import io
import os
import tempfile
import zipfile

import PyPDF2
import requests
import streamlit as st
from PIL import Image

# API_URL = "https://api.vaarhaft.com/v2/fraudscanner"
API_KEY = os.getenv("API_KEY")

# --- Streamlit UI ---

st.title("VAARHAFT API Demo")

stage = st.selectbox(
    "Stage",
    ("Production", "Dev", "Local"),
)

match stage:
    case "Production":
        API_URL = "https://api.vaarhaft.com/v2/fraudscanner"
    case "Dev":
        API_URL = "https://0nx6soggmd.execute-api.eu-central-1.amazonaws.com/dev/v2/fraudscanner"
    case "Local":
        API_URL = "http://127.0.0.1:9999/fraudScanner_v2"
    case _:
        st.error("Ungültige Stage ausgewählt. Bitte wählen Sie Prod, Dev oder Local.")


# Custom headers input
st.subheader("Header-Informationen der Anfrage")

API_KEY = st.text_input(
    "API Key",
    placeholder="Geben Sie Ihren API Key ein",
    value=API_KEY if API_KEY else "",
    type="password",  # Hide the input for security
)

# Initialize case_nr in session state if it doesn't exist
if "case_nr" not in st.session_state:
    st.session_state.case_nr = ""

# Get the case number from the text input
case_nr = st.text_input("Fallnummer", placeholder="Case 1A-421", max_chars=35, key="case_nr")

# Check for minimum length and display appropriate warnings
if not case_nr:
    st.warning("Bitte geben Sie eine Fallnummer ein, um die Anfrage zu identifizieren.")
elif len(case_nr) < 4:
    st.warning("Die Fallnummer muss mindestens 4 Zeichen lang sein.")
# issue_date = st.text_input("Falldatum", placeholder="16.04.2023")
issue_date = st.date_input("Falldatum", value=None, help="Optional: Geben Sie das Datum des Falls an.")

# use_default_headers = st.checkbox("Use default headers", value=True)
custom_headers = {}

# if not use_default_headers:
# st.write("Enter custom headers (one per line in format 'key: value'):")
# custom_headers_text = st.text_area("Custom Headers", height=100)
# if custom_headers_text:
#     for line in custom_headers_text.split("\n"):
#         if ":" in line:
#             key, value = line.split(":", 1)
#             custom_headers[key.strip()] = value.strip()
custom_headers["x-api-key"] = API_KEY
custom_headers["caseNumber"] = case_nr
# Don't set Content-Type for file uploads as it will be set automatically by requests

# Allow multiple files to be uploaded
uploaded_files = st.file_uploader("Dateien auswählen", type=["jpg", "jpeg", "png", "heic", "webp", "pdf"], accept_multiple_files=True)
# Preview uploaded files
if uploaded_files:
    st.subheader("Vorschau der einzureichenden Dateien")

    for i, uploaded_file in enumerate(uploaded_files):
        col1, col2 = st.columns([1, 3])
        if uploaded_file.name.lower().endswith(".pdf"):
            pdf_reader = PyPDF2.PdfReader(uploaded_file)

        with col1:
            st.write(f"**Dateiname:** {uploaded_file.name}")
            if uploaded_file.size > 1_000_000:
                size_str = f"{uploaded_file.size / 1_000_000:.2f} mb"
            elif uploaded_file.size > 1_000:
                size_str = f"{uploaded_file.size / 1000:.1f} kb"
            else:
                size_str = f"{uploaded_file.size} bytes"
            st.write(f"**Größe:** {size_str}")
            if uploaded_file.name.lower().endswith(".pdf"):
                st.write(f"**Seiten:** {len(pdf_reader.pages)}")

        with col2:
            # Preview based on file type
            if uploaded_file.name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".heic")):
                image = Image.open(uploaded_file)
                st.image(image, caption=uploaded_file.name, width=300)
                # Reset file pointer after reading
                uploaded_file.seek(0)
            elif uploaded_file.name.lower().endswith(".pdf"):
                try:
                    image = Image.open("resources/pdf-logo.png")
                    st.image(image, caption=uploaded_file.name, width=300)
                    # Reset file pointer after reading
                    uploaded_file.seek(0)
                except Exception as e:
                    st.error(f"Fehler bei der PDF Vorschau: {e}")
            if i != len(uploaded_files) - 1:
                st.write("---")

    st.info("Bereit zum Upload!")

    # Button to trigger upload & processing
    if st.button("Anfrage an die VAARHAFT API senden"):
        if not uploaded_files:
            st.error("Bitte mindestens eine Datei auswählen, bevor Sie die Anfrage senden.")
        else:
            with st.spinner("Dateien werden verarbeitet und hochgeladen..."):
                # Create a temporary zip file containing all uploaded files
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip_file:
                    with zipfile.ZipFile(temp_zip_file.name, "w") as zip_file:
                        for uploaded_file in uploaded_files:
                            # Write each file to the zip
                            zip_file.writestr(uploaded_file.name, uploaded_file.getvalue())

                # Prepare headers
                headers = {"Authorization": f"Bearer {API_KEY}"}
                # if not use_default_headers and custom_headers:
                #     headers.update(custom_headers)
                headers.update(custom_headers)

                # Open the zip file and send it to the API
                with open(temp_zip_file.name, "rb") as f:
                    files = {"file": (os.path.basename(temp_zip_file.name), f, "application/zip")}

                    # Send POST request to API
                    response = requests.post(API_URL, files=files, headers=headers)

                # Clean up the temporary file
                os.unlink(temp_zip_file.name)

                # Process the response
                if response.status_code == 200:
                    st.success("Anfrage erfolgreich.")

                    # Check if response is multipart or JSON
                    content_type = response.headers.get("Content-Type", "")

                    if "multipart/form-data" in content_type or "multipart/mixed" in content_type:
                        # Handle multipart response (JSON + zip files)
                        st.write("Multipart-Response erhalten")

                        # First try to extract JSON data
                        json_data = None
                        try:
                            # Try to parse the response content as text first
                            content_str = response.text

                            # Try to find JSON part in the multipart response
                            import re

                            # Look for Content-Type: application/json header followed by JSON content
                            json_header_match = re.search(
                                r"Content-Type:\s*application/json.*?\r\n\r\n(.*?)(?:\r\n--|--%)", content_str, re.DOTALL | re.IGNORECASE
                            )

                            if json_header_match:
                                potential_json = json_header_match.group(1).strip()

                                # Preprocess the JSON text to fix formatting issues
                                processed_json = potential_json

                                # Check if we need to add commas (if the JSON is formatted with newlines instead of commas)
                                if "{\n" in processed_json or "}\n" in processed_json:
                                    # Split by newlines and filter out empty lines
                                    lines = [line.strip() for line in processed_json.split("\n") if line.strip()]

                                    # Process each line
                                    for line_idx in range(len(lines) - 1):
                                        # If this line ends with a value (not { or [) and next line starts with a key (not } or ])
                                        if (
                                            lines[line_idx].endswith('"')
                                            or lines[line_idx].endswith("}")
                                            or lines[line_idx].endswith("]")
                                            or lines[line_idx].endswith("true")
                                            or lines[line_idx].endswith("false")
                                            or lines[line_idx].endswith("null")
                                            or any(lines[line_idx].endswith(str(n)) for n in range(10))
                                        ):
                                            if lines[line_idx + 1].strip().startswith('"') or lines[line_idx + 1].strip().startswith("}"):
                                                # Add a comma if needed
                                                if not lines[line_idx].endswith(","):
                                                    lines[line_idx] = lines[line_idx] + ","

                                    # Rejoin the lines
                                    processed_json = "\n".join(lines)

                                try:
                                    # Try to parse with the original text first
                                    import json

                                    try:
                                        json_data = json.loads(potential_json)
                                    except json.JSONDecodeError:
                                        # If that fails, try with the processed text
                                        try:
                                            # Remove any trailing commas before closing braces or brackets
                                            processed_json = re.sub(r",\s*}", "}", processed_json)
                                            processed_json = re.sub(r",\s*]", "]", processed_json)

                                            # Try to parse the processed text
                                            json_data = json.loads(processed_json)
                                        except json.JSONDecodeError:
                                            # If still failing, try a more aggressive approach: convert to a single line
                                            single_line = re.sub(r"\n\s*", " ", processed_json)
                                            # Add missing commas between key-value pairs
                                            single_line = re.sub(r'"\s+("|\}|\])', '", \1', single_line)
                                            # Remove any trailing commas before closing braces or brackets
                                            single_line = re.sub(r",\s*}", "}", single_line)
                                            single_line = re.sub(r",\s*]", "]", single_line)

                                            json_data = json.loads(single_line)

                                    st.subheader("JSON-Antwort")
                                    st.json(json_data)
                                except json.JSONDecodeError:
                                    # Continue to next approach if this fails
                                    pass

                            # If the above approach failed, fall back to the original regex approach
                            if not json_data:
                                # Look for JSON-like content (starting with { and ending with })
                                json_match = re.search(r"({.*})", content_str, re.DOTALL)
                                if json_match:
                                    potential_json = json_match.group(1)
                                    try:
                                        import json

                                        json_data = json.loads(potential_json)
                                        st.subheader("JSON-Antwort")
                                        st.json(json_data)
                                    except json.JSONDecodeError:
                                        # Continue to next approach if this fails
                                        pass

                            # If regex approach failed, try direct parsing as fallback
                            if not json_data:
                                try:
                                    json_data = response.json()
                                    st.subheader("JSON-Antwort")
                                    st.json(json_data)
                                except Exception:
                                    st.warning("JSON Inhalte der Antwort konnten nicht korrekt geparsed werden")
                        except Exception:
                            st.warning("Fehler bei der Verarbeitung der Multipart-Response")

                        # Check if there are any zip files in the response
                        # This assumes the API returns zip files as part of the JSON response
                        # with URLs or base64 encoded content

                        # Try to extract binary parts from multipart response
                        try:
                            # Check if we can find boundary in content-type header
                            import re

                            boundary_match = re.search(r"boundary=([^;]+)", content_type)

                            if boundary_match:
                                boundary = boundary_match.group(1).strip("\"'")

                                # Split the content by boundary
                                parts = response.content.split(f"--{boundary}".encode())

                                # Process each part
                                for i, part in enumerate(parts):
                                    if i == 0 or not part or part.startswith(b"--"):  # Skip empty parts or end marker
                                        continue

                                    # Try to determine if this part is binary (zip) or text
                                    # Look for Content-Type header in this part
                                    part_header_end = part.find(b"\r\n\r\n")
                                    if part_header_end > 0:
                                        part_header = part[:part_header_end].decode("utf-8", errors="ignore")
                                        part_body = part[part_header_end + 4 :]  # Skip the \r\n\r\n

                                        # Check if this part contains JSON
                                        if "application/json" in part_header.lower() or "text/json" in part_header.lower():
                                            try:
                                                part_text = part_body.decode("utf-8", errors="ignore")
                                                import json

                                                # Preprocess the JSON text to fix formatting issues
                                                # Replace newlines between key-value pairs with commas
                                                processed_text = part_text.strip()

                                                # Check if we need to add commas (if the JSON is formatted with newlines instead of commas)
                                                if "{\n" in processed_text or "}\n" in processed_text:
                                                    # Split by newlines and filter out empty lines
                                                    lines = [line.strip() for line in processed_text.split("\n") if line.strip()]

                                                    # Process each line
                                                    for line_idx in range(len(lines) - 1):
                                                        # If this line ends with a value (not { or [) and next line starts with a key (not } or ])
                                                        if (
                                                            lines[line_idx].endswith('"')
                                                            or lines[line_idx].endswith("}")
                                                            or lines[line_idx].endswith("]")
                                                            or lines[line_idx].endswith("true")
                                                            or lines[line_idx].endswith("false")
                                                            or lines[line_idx].endswith("null")
                                                            or any(lines[line_idx].endswith(str(n)) for n in range(10))
                                                        ):
                                                            if lines[line_idx + 1].strip().startswith('"') or lines[line_idx + 1].strip().startswith(
                                                                "}"
                                                            ):
                                                                # Add a comma if needed
                                                                if not lines[line_idx].endswith(","):
                                                                    lines[line_idx] = lines[line_idx] + ","

                                                    # Rejoin the lines
                                                    processed_text = "\n".join(lines)

                                                # Try to parse with the original text first
                                                try:
                                                    part_json = json.loads(part_text)
                                                except json.JSONDecodeError:
                                                    # If that fails, try with the processed text
                                                    try:
                                                        # Remove any trailing commas before closing braces or brackets
                                                        processed_text = re.sub(r",\s*}", "}", processed_text)
                                                        processed_text = re.sub(r",\s*]", "]", processed_text)

                                                        # Try to parse the processed text
                                                        part_json = json.loads(processed_text)
                                                    except json.JSONDecodeError:
                                                        # If still failing, try a more aggressive approach: convert to a single line
                                                        try:
                                                            # Convert to a single line and fix common issues
                                                            single_line = re.sub(r"\n\s*", " ", processed_text)
                                                            # Add missing commas between key-value pairs
                                                            single_line = re.sub(r'"\s+("|\}|\])', '", \1', single_line)
                                                            # Remove any trailing commas before closing braces or brackets
                                                            single_line = re.sub(r",\s*}", "}", single_line)
                                                            single_line = re.sub(r",\s*]", "]", single_line)

                                                            part_json = json.loads(single_line)
                                                        except json.JSONDecodeError as e:
                                                            raise e

                                                # Store this as our json_data if we haven't found any yet
                                                if not json_data:
                                                    json_data = part_json
                                                    st.subheader("JSON-Antwort")
                                                    st.json(part_json)
                                            except Exception:
                                                st.warning("Fehler beim Parsen von JSON")

                                        # Check if this part is a zip file
                                        elif b"PK\x03\x04" in part_body[:10]:  # ZIP file signature
                                            try:
                                                with zipfile.ZipFile(io.BytesIO(part_body)) as zip_ref:
                                                    # Use a unique subheader for each zip file
                                                    zip_filename = f"FraudScanner_part{i}.zip"

                                                    # Try to extract a more meaningful name from the Content-Disposition header if available
                                                    content_disp_match = re.search(r'filename="([^"]+)"', part_header)
                                                    if content_disp_match:
                                                        zip_filename = content_disp_match.group(1)

                                                    st.subheader(f"Inhalte der Zip-Datei: {zip_filename}")
                                                    st.download_button(
                                                        f"Zip-Datei herunterladen: {zip_filename}",
                                                        data=part_body,
                                                        file_name=zip_filename,
                                                        on_click="ignore",
                                                    )

                                                    # Preview zip contents
                                                    file_list = zip_ref.namelist()
                                                    st.write("Inhalte:")
                                                    for file_name in file_list:
                                                        st.write(f"- {file_name}")

                                                        # Preview images in the zip
                                                        if file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".heic")):
                                                            with zip_ref.open(file_name) as file:
                                                                image = Image.open(file)
                                                                st.image(image, caption=file_name, width=300)
                                                        # Preview PDFs in the zip
                                                        elif file_name.lower().endswith(".pdf"):
                                                            try:
                                                                with zip_ref.open(file_name) as file:
                                                                    # Create a temporary file to save the PDF
                                                                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                                                                        temp_pdf.write(file.read())
                                                                        temp_pdf_path = temp_pdf.name

                                                                    # Read the PDF to get page count
                                                                    pdf_reader = PyPDF2.PdfReader(temp_pdf_path)
                                                                    st.write(f"PDF mit {len(pdf_reader.pages)} Seiten")

                                                                    # Provide a download button for the PDF
                                                                    with open(temp_pdf_path, "rb") as pdf_file:
                                                                        pdf_bytes = pdf_file.read()
                                                                        st.download_button(
                                                                            f"Datei herunterladen: {file_name}",
                                                                            data=pdf_bytes,
                                                                            file_name=file_name,
                                                                            mime="application/pdf",
                                                                            on_click="ignore",
                                                                        )

                                                                    # Clean up the temporary file
                                                                    os.unlink(temp_pdf_path)
                                                            except Exception as e:
                                                                st.warning(f"Fehler beim Anzeigen der PDF-Datei: {e}")
                                            except zipfile.BadZipFile:
                                                st.warning("Die Zip-Datei konnte nicht geöffnet werden")

                            # Fallback: If we couldn't parse multipart properly, try the entire content as a zip
                            if not boundary_match and response.content and not json_data:
                                try:
                                    # Try to treat the entire response as a zip file
                                    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                                        st.subheader("Inhalte der Zip-Datei")
                                        st.download_button(
                                            "Zip-Datei herunterladen",
                                            data=response.content,
                                            file_name="FraudScanner.zip",
                                            on_click="ignore",
                                        )

                                        # Preview zip contents
                                        file_list = zip_ref.namelist()
                                        st.write("Inhalte:")
                                        for file_name in file_list:
                                            st.write(f"- {file_name}")

                                            # Preview images in the zip
                                            if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                                                with zip_ref.open(file_name) as file:
                                                    image = Image.open(file)
                                                    st.image(image, caption=file_name, width=300)
                                            # Preview PDFs in the zip
                                            elif file_name.lower().endswith(".pdf"):
                                                try:
                                                    with zip_ref.open(file_name) as file:
                                                        # Create a temporary file to save the PDF
                                                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                                                            temp_pdf.write(file.read())
                                                            temp_pdf_path = temp_pdf.name

                                                        # Read the PDF to get page count
                                                        pdf_reader = PyPDF2.PdfReader(temp_pdf_path)
                                                        st.write(f"PDF with {len(pdf_reader.pages)} pages")

                                                        # Provide a download button for the PDF
                                                        with open(temp_pdf_path, "rb") as pdf_file:
                                                            pdf_bytes = pdf_file.read()
                                                            st.download_button(
                                                                f"Download {file_name}",
                                                                data=pdf_bytes,
                                                                file_name=file_name,
                                                                mime="application/pdf",
                                                                on_click="ignore",
                                                            )

                                                        # Clean up the temporary file
                                                        os.unlink(temp_pdf_path)
                                                except Exception as e:
                                                    st.warning(f"Fehler beim Anzeigen der PDF-Datei: {e}")
                                except zipfile.BadZipFile:
                                    st.warning("Die Antwort enthält keine gültige Zip-Datei")
                                    st.download_button(
                                        "Stattdessen rohe Antwort herunterladen",
                                        data=response.content,
                                        file_name="response.bin",
                                        on_click="ignore",
                                    )
                        except Exception:
                            st.warning("Die Antwort konnte nicht verarbeitet werden")
                            st.download_button(
                                "Rohe Antwort herunterladen",
                                data=response.content,
                                file_name="response.bin",
                                on_click="ignore",
                            )

                        # If JSON data contains references to zip files
                        if json_data:
                            # Check for common patterns in JSON that might indicate zip files
                            for key, value in json_data.items():
                                if isinstance(value, str) and value.endswith(".zip"):
                                    # This could be a URL to a zip file
                                    st.subheader(f"Zip-Datei: {key}")
                                    try:
                                        zip_response = requests.get(value, headers=headers)
                                        if zip_response.status_code == 200:
                                            st.download_button(
                                                f"Download {key}",
                                                data=zip_response.content,
                                                file_name=f"{key}.zip",
                                                on_click="ignore",
                                            )

                                            # Preview zip contents
                                            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zip_ref:
                                                file_list = zip_ref.namelist()
                                                st.write("Inhalte:")
                                                for file_name in file_list:
                                                    st.write(f"- {file_name}")

                                                    # Preview images in the zip
                                                    if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                                                        with zip_ref.open(file_name) as file:
                                                            image = Image.open(file)
                                                            st.image(image, caption=file_name, width=300)
                                                    # Preview PDFs in the zip
                                                    elif file_name.lower().endswith(".pdf"):
                                                        try:
                                                            with zip_ref.open(file_name) as file:
                                                                # Create a temporary file to save the PDF
                                                                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                                                                    temp_pdf.write(file.read())
                                                                    temp_pdf_path = temp_pdf.name

                                                                # Read the PDF to get page count
                                                                pdf_reader = PyPDF2.PdfReader(temp_pdf_path)
                                                                st.write(f"PDF with {len(pdf_reader.pages)} pages")

                                                                # Provide a download button for the PDF
                                                                with open(temp_pdf_path, "rb") as pdf_file:
                                                                    pdf_bytes = pdf_file.read()
                                                                    st.download_button(
                                                                        f"Download {file_name}",
                                                                        data=pdf_bytes,
                                                                        file_name=file_name,
                                                                        mime="application/pdf",
                                                                        on_click="ignore",
                                                                    )
                                                                # Clean up the temporary file
                                                                os.unlink(temp_pdf_path)
                                                        except Exception as e:
                                                            st.warning(f"Fehler beim Anzeigen der PDF-Datei: {e}")
                                    except Exception as e:
                                        st.error(f"Fehler beim Herunterladen oder Verarbeiten der Zip-Datei: {e}")
                    else:
                        # Handle JSON-only response
                        try:
                            json_data = response.json()
                            st.subheader("JSON-Antwort")
                            st.json(json_data)
                        except:
                            st.error("JSON-Antwort konnte nicht korrekt geparsed werden")
                            st.text(response.text)
                else:
                    st.error(f"Die Anfrage schlug mit Statuscode {response.status_code} fehl.")
                    st.text(response.text)
