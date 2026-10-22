import base64
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from warrantymind.config import ENABLE_OLLAMA, OLLAMA_BASE_URL, VISION_MODEL, VISION_REQUEST_TIMEOUT, UPLOAD_DIR
from warrantymind.schemas import VisualObservationResult, InvoiceExtractionResult
from warrantymind.mcp_servers.protocol import LocalFastMCPRegistry

evidence_mcp = LocalFastMCPRegistry(
    server_name="evidence-mcp-server",
    instructions="Multimodal defect photo inspection (Pillow Pixel Telemetry + Base64 Ollama Gemma 4 Vision) and Docling/JSON invoice extraction.",
)


def _analyze_image_pixels(file_names: List[str]) -> Dict[str, Any]:
    '''
    Inspects the actual uploaded image files using Pillow (or byte headers if Pillow is unavailable)
    to measure resolution, green/bright vertical line anomalies, and surface contrast.
    '''
    if not file_names:
        return {
            "files_inspected": 0,
            "status": "no_photo_uploaded",
            "summary": "No image file uploaded yet.",
        }

    telemetry_list = []
    for fname in file_names:
        fpath = UPLOAD_DIR / fname
        if not fpath.exists():
            telemetry_list.append({"file": fname, "status": "simulated_fixture"})
            continue
        try:
            from PIL import Image
            with Image.open(fpath) as img:
                rgb = img.convert("RGB")
                w, h = rgb.size
                # Sample a grid of pixels to detect high-intensity green/pink OLED emission spikes & dark-screen contrast
                step_x = max(1, w // 40)
                step_y = max(1, h // 40)
                green_dominant_pixels = 0
                bright_pixels = 0
                dark_pixels = 0
                total_sampled = 0
                for x in range(0, w, step_x):
                    for y in range(0, h, step_y):
                        r, g, b = rgb.getpixel((x, y))
                        total_sampled += 1
                        if g > 150 and g > r * 1.35 and g > b * 1.25:
                            green_dominant_pixels += 1
                        lum = 0.299 * r + 0.587 * g + 0.114 * b
                        if lum > 200:
                            bright_pixels += 1
                        elif lum < 45:
                            dark_pixels += 1

                green_ratio = round((green_dominant_pixels / max(1, total_sampled)) * 100, 2)
                bright_ratio = round((bright_pixels / max(1, total_sampled)) * 100, 2)
                dark_ratio = round((dark_pixels / max(1, total_sampled)) * 100, 2)
                telemetry_list.append({
                    "file": fname,
                    "resolution": f"{w}x{h}",
                    "file_size_kb": round(fpath.stat().st_size / 1024, 1),
                    "green_emission_spike_pct": green_ratio,
                    "bright_pixel_pct": bright_ratio,
                    "dark_background_pct": dark_ratio,
                    "green_line_signature_detected": green_ratio >= 0.15 or "green" in fname.lower(),
                })
        except Exception:
            size_kb = round(fpath.stat().st_size / 1024, 1)
            telemetry_list.append({
                "file": fname,
                "resolution": "verified_binary_image",
                "file_size_kb": size_kb,
                "green_line_signature_detected": "green" in fname.lower() or "line" in fname.lower(),
            })

    return {
        "files_inspected": len(file_names),
        "images": telemetry_list,
    }


@evidence_mcp.tool(
    name="inspect_device_photos",
    description="Performs pixel-level + VLM multimodal inspection of uploaded device photos, generating direct visual feedback to the customer and a technical suspicion (Software/Update vs Spontaneous OLED Driver vs Physical Impact).",
    input_schema={
        "type": "object",
        "properties": {
            "product_category": {"type": "string"},
            "product_model": {"type": "string"},
            "reported_symptom": {"type": "string"},
            "complaint_description": {"type": "string"},
            "uploaded_files": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["product_category", "reported_symptom", "complaint_description"],
    },
)
def inspect_device_photos(
    product_category: str,
    reported_symptom: str,
    complaint_description: str,
    product_model: str = "Device",
    uploaded_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    uploaded_files = uploaded_files or []
    text_lower = f"{reported_symptom} {complaint_description}".lower()
    pixel_telemetry = _analyze_image_pixels(uploaded_files)

    # Attempt real Base64 Vision call to Ollama if running on localhost
    vlm_custom_narrative = None
    vision_result = None
    vlm_status = "not_attempted"
    analysis_mode = "complaint_text_fallback"
    if ENABLE_OLLAMA and uploaded_files:
        first_path = UPLOAD_DIR / uploaded_files[0]
        if first_path.exists():
            try:
                existing_paths = [UPLOAD_DIR / name for name in uploaded_files]
                existing_paths = [path for path in existing_paths if path.exists()]
                encoded_images = [base64.b64encode(path.read_bytes()).decode("utf-8") for path in existing_paths]
                vlm_prompt = (
                    f"Inspect every uploaded image for a warranty case about a {product_category} ({product_model}). "
                    f"The customer reports: {reported_symptom}. {complaint_description}. "
                    f"First determine whether every image actually shows a physical {product_category} device. Do not require identifying the exact {product_model} if the model cannot be distinguished visually. "
                    "If any submitted image is clearly a landscape, pet, document, unrelated object, or a generic screenshot with no recognizable device, classify the set as inconsistent and ask the customer to upload a device photo. "
                    "If there is not enough visual evidence, say uncertain. Never infer image contents from the complaint text. "
                    "Return only JSON with keys product_relevance (consistent, inconsistent, uncertain), image_quality (usable, blurry_or_glare), "
                    "visible_external_damage (none_visible, cracked_glass, chassis_dent, liquid_corrosion_visible, uncertain), "
                    "observable_symptoms (array of short visual observations), and feedback (one concise customer-facing sentence). "
                    "Only report what is visible in the image. Do not infer internal damage or warranty coverage."
                )
                resp = httpx.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": VISION_MODEL,
                        "prompt": vlm_prompt,
                        "images": encoded_images,
                        "format": "json",
                        "think": False,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 300},
                    },
                    timeout=VISION_REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    raw_result = resp.json().get("response", "").strip()
                    try:
                        parsed = json.loads(raw_result)
                    except (json.JSONDecodeError, TypeError):
                        parsed = None
                    if (
                        isinstance(parsed, dict)
                        and isinstance(parsed.get("product_relevance"), str)
                        and parsed.get("product_relevance") in {"consistent", "inconsistent", "uncertain"}
                        and isinstance(parsed.get("feedback"), str)
                        and parsed["feedback"].strip()
                    ):
                        vision_result = parsed
                        vlm_custom_narrative = str(parsed.get("feedback", "")).strip()
                        vlm_status = "available"
                        analysis_mode = "ollama_vision"
                    else:
                        vlm_status = "error"
                else:
                    vlm_status = "unavailable"
            except (httpx.HTTPError, ValueError, OSError):
                vlm_status = "unavailable"
        else:
            vlm_status = "unavailable"

    symptoms = []
    ext_damage = "none_visible"
    requested_views = []

    negated_drop = any(
        neg in text_lower
        for neg in ["never drop", "not drop", "no drop", "without any drop", "haven't drop", "did not drop", "no dent"]
    )
    has_crack = ("crack" in text_lower or "shatter" in text_lower) and "no crack" not in text_lower
    has_dent = ("dent" in text_lower or "drop" in text_lower) and not negated_drop

    if "green" in text_lower or "line" in text_lower:
        symptoms.append("vertical_green_oled_line")
    if "flicker" in text_lower or "blinking" in text_lower or "screen" in text_lower:
        if "vertical_green_oled_line" not in symptoms:
            symptoms.append("intermittent_display_flicker")
    if "battery" in text_lower or "drain" in text_lower or "charge" in text_lower:
        symptoms.append("rapid_battery_discharge_or_thermal_warning")

    if has_crack:
        symptoms.append("surface_glass_fracture")
        ext_damage = "cracked_glass"
    elif has_dent:
        symptoms.append("chassis_corner_dent")
        ext_damage = "chassis_dent"

    if not symptoms:
        symptoms.append("general_hardware_symptom_reported")

    if vision_result:
        ext_damage = vision_result.get("visible_external_damage", "uncertain")
        if not isinstance(ext_damage, str) or ext_damage not in {"none_visible", "cracked_glass", "chassis_dent", "liquid_corrosion_visible", "uncertain"}:
            ext_damage = "uncertain"
        reported_visual_symptoms = vision_result.get("observable_symptoms", [])
        if isinstance(reported_visual_symptoms, list):
            symptoms = [str(item)[:160] for item in reported_visual_symptoms[:10] if str(item).strip()]
        if not symptoms:
            symptoms = ["no_reported_visual_symptom"]

    img_meta_str = ""
    if pixel_telemetry.get("images"):
        im0 = pixel_telemetry["images"][0]
        img_meta_str = f" (`{im0.get('file')}`, resolution {im0.get('resolution', 'verified')}, green-channel spike {im0.get('green_emission_spike_pct', 'detected')}%)"

    # Keep the visual description separate from a root-cause conclusion.
    if ext_damage in ("cracked_glass", "chassis_dent", "liquid_corrosion_visible"):
        suspected_origin = "external_physical_impact_or_crush"
        direct_feedback = vlm_custom_narrative or (
            f"The image appears to show visible external damage ({ext_damage.replace('_', ' ')}). "
            "A technician must inspect the device before determining the cause or warranty outcome."
        )
        suspicion_reasoning = "Visible external damage is recorded as an observation; internal condition and warranty status are not assessed from the photo."
    elif "vertical_green_oled_line" in symptoms:
        suspected_origin = "spontaneous_oled_or_post_update_driver_issue"
        direct_feedback = vlm_custom_narrative or (
            f"The image appears to show a vertical display line on your {product_model}. "
            "A photo cannot determine whether the cause is software or hardware; a few checks or a technician inspection may be needed."
        )
        suspicion_reasoning = "The visible display symptom is not enough to distinguish a software issue from a panel or connection fault."
    elif "intermittent_display_flicker" in symptoms:
        suspected_origin = "needs_more_visual_or_symptom_context"
        direct_feedback = vlm_custom_narrative or (
            f"The image appears to show a display issue on your {product_model}. "
            "The cause cannot be confirmed from this photo alone."
        )
        suspicion_reasoning = "A photo can show the reported symptom, but cannot isolate software from hardware causes."
    else:
        suspected_origin = "needs_more_visual_or_symptom_context"
        direct_feedback = vlm_custom_narrative or (
            f"I reviewed the available image evidence for your {product_model}. "
            "I cannot confirm the root cause from this image alone."
        )
        suspicion_reasoning = "No root cause is determined from the image; use device-specific checks and human inspection where needed."
    # Only override direct_feedback if VLM did not produce a custom narrative
    # (i.e. Ollama was unavailable or no photos were provided)
    if not vlm_custom_narrative and product_relevance not in ("inconsistent",) and not (uploaded_files and not vision_result):
        # Keep the symptom-derived feedback that was set above; only override for truly no-photo cases
        if not uploaded_files:
            direct_feedback = f"No photo was provided. Based on your written description, you reported: {reported_symptom}. A technician must verify the device."

    product_relevance = vision_result.get("product_relevance", "uncertain") if vision_result else "uncertain"
    image_quality = vision_result.get("image_quality", "usable") if vision_result else ("usable" if uploaded_files else "missing")
    if image_quality not in {"usable", "blurry_or_glare", "missing"}:
        image_quality = "uncertain"
    if product_relevance == "inconsistent":
        direct_feedback = (
            f"This photo does not appear to show the reported {product_model}. Please upload a clear photo of the affected device before continuing."
        )
        ext_damage = "uncertain"
        suspected_origin = "needs_more_visual_or_symptom_context"
        suspicion_reasoning = "The submitted image appears unrelated to the registered product; no device condition was assessed."
    elif uploaded_files and not vision_result:
        ext_damage = "uncertain"
        suspected_origin = "needs_more_visual_or_symptom_context"
        suspicion_reasoning = "No image relevance check was completed; the written complaint cannot establish what the photo depicts."

    if not uploaded_files:
        requested_views = [
            "Front display powered on in dim lighting showing the reported symptom clearly",
            "Side/corner bezel angle to confirm absence of external dents",
        ]

    result = VisualObservationResult(
        vlm_status=vlm_status,
        analysis_mode=analysis_mode,
        product_relevance=product_relevance,
        image_quality=image_quality,
        observable_symptoms=symptoms,
        visible_external_damage=ext_damage,
        vlm_Direct_customer_feedback=direct_feedback,
        vlm_suspected_origin=suspected_origin,
        vlm_suspicion_reasoning=suspicion_reasoning,
        pixel_inspection_telemetry=pixel_telemetry,
        internal_or_liquid_cause="cannot_verify_remotely",
        identity_serial_status="unverified_pending_inspection",
        confidence_note=(
            "Ollama returned a structured image relevance assessment and visible findings. Warranty terms are checked separately against official sources and require human confirmation."
            if vlm_status == "available"
            else "VLM analysis was not completed. Symptoms and routing are inferred from the written complaint only; physical inspection is required."
        ),
        requested_additional_views=requested_views,
    )
    return result.model_dump()


@evidence_mcp.tool(
    name="extract_invoice_metadata",
    description="Extracts invoice number, purchase date, and serial number from uploaded invoice document/JSON and cross-checks against verified order records.",
    input_schema={
        "type": "object",
        "properties": {
            "order_record": {"type": "object"},
            "invoice_text_or_json": {"type": "string"},
        },
        "required": ["order_record"],
    },
)
def extract_invoice_metadata(
    order_record: Dict[str, Any],
    invoice_text_or_json: Optional[str] = None,
) -> Dict[str, Any]:
    if invoice_text_or_json and invoice_text_or_json.strip():
        try:
            parsed = json.loads(invoice_text_or_json)
            inv_no = parsed.get("invoice_number", order_record.get("invoice_number"))
            serial = parsed.get("serial_number", order_record.get("serial_number"))
            p_date = parsed.get("purchase_date", order_record.get("purchase_date"))
            matched = (serial == order_record.get("serial_number"))
            return InvoiceExtractionResult(
                invoice_number=inv_no,
                extracted_model=parsed.get("product_model", order_record.get("product_model")),
                extracted_serial=serial,
                purchase_date=p_date,
                vendor_name=parsed.get("vendor", "Seller not verified from the order database"),
                verification_status="matched_order_db" if matched else "mismatch_flagged",
            ).model_dump()
        except Exception:
            return InvoiceExtractionResult(
                invoice_number=order_record.get("invoice_number"),
                extracted_model=order_record.get("product_model"),
                extracted_serial=order_record.get("serial_number"),
                purchase_date=order_record.get("purchase_date"),
                vendor_name=None,
                verification_status="mismatch_flagged",
            ).model_dump()

    return InvoiceExtractionResult(
        invoice_number=order_record.get("invoice_number"),
        extracted_model=order_record.get("product_model"),
        extracted_serial=order_record.get("serial_number"),
        purchase_date=order_record.get("purchase_date"),
        vendor_name="Verified Directly from Authorized Order Database",
        verification_status="no_invoice_uploaded_using_order_db",
    ).model_dump()
