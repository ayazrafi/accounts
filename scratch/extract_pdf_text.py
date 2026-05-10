import sys
try:
    import pypdf
    reader = pypdf.PdfReader(r"d:\WRMSWork\Accounts\accounts\credit_note_from_image.pdf")
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    print(text)
except Exception as e:
    print(f"Error: {e}")
