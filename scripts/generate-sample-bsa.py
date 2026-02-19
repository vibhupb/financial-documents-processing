#!/usr/bin/env python3
"""Fill the existing BSA Profile template with synthetic John/Jane Doe data."""

import os
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'BSA Profile NEW 2 1 3.pdf')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'tests', 'sample-documents')
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT = os.path.join(OUTPUT_DIR, 'sample-bsa-profile-filled.pdf')

# Synthetic data for form fields
FIELD_DATA = {
    # Section 1: Legal Entity
    "Company Name": "Doe Industries LLC",
    "DBA/Parent Co Name": "Doe Tech Solutions",
    "Entity Type": "Limited Liability Company",
    "Tax ID Number": "82-1234567",
    "Tax ID if different for filing purposes": "",
    "Date Entity Established": "03/15/2018",
    "State of Incorporation": "Delaware",
    "Country of Incorporation": "United States",
    "NAICS Code": "541511",
    "Business Phone": "(512) 555-0142",
    "Business Phone 1": "(512) 555-0143",
    "Fax Number": "(512) 555-0144",
    "Business Web Address": "www.doeindustries.com",
    "Yes No If yes please provide detailsMailing Address": "1234 Innovation Drive, Suite 500, Austin, TX 78701",
    "Yes No If yes please provide the countries in which the entity conducts business": "United States, Canada",

    # Beneficial Owner 1 - John Doe (Control Person, 60%)
    "Full Legal name": "John Michael Doe",
    "Professional Title": "Managing Member / CEO",
    "Date of Birth": "07/22/1985",
    "Email Address": "john.doe@doeindustries.com",
    "MobileOther": "(512) 555-0150",
    "Physical Address cannot be a PO box": "5678 Maple Avenue, Austin, TX 78702",
    "Mailing Address if different than above": "",
    "Type": "Driver's License",
    "Identification Number": "DL-98765432",
    "Issuance Date": "11/22/2023",
    "Expiration Date": "11/22/2028",
    "Country of Citizenship": "United States",
    "Country of Residency": "United States",
    "Percentage of ownership": "60%",

    # Beneficial Owner 2 - Jane Doe (CFO, 40%)
    "Full Legal name_2": "Jane Elizabeth Doe",
    "Professional Title_2": "Chief Financial Officer",
    "Date of Birth_2": "03/14/1988",
    "Email Address_2": "jane.doe@doeindustries.com",
    "MobileOther_2": "(512) 555-0151",
    "Physical Address cannot be a PO box_2": "5678 Maple Avenue, Austin, TX 78702",
    "Mailing Address if different than above_2": "",
    "Type_2": "US Passport",
    "Identification Number_2": "P-567891234",
    "Issuance Date_2": "06/30/2020",
    "Expiration Date_2": "06/30/2030",
    "Country of Citizenship_2": "United States",
    "Country of Residency_2": "United States",
    "Percentage of ownership_2": "40%",

    # Owner 3-6 left blank (only 2 owners)
    "Full Legal name_3": "",
    "Full Legal name_4": "",
    "Full Legal name_5": "",

    # Trust info (not a trust)
    "Trust name": "",
    "Full legal name of trustee": "",

    # Risk/other
    "PEP": "No",
    "Real Estate Project Description": "",
    "Text3": "Custom software development and SaaS platform licensing",
    "Text67": "John Michael Doe",
    "Text97": "01/15/2026",
    "Text98": "Sarah K. Williams, VP BSA/AML Compliance",
}

# Checkboxes to check (value /Yes)
CHECKBOXES_ON = {
    "Check Box1",   # Typical: entity is not an individual
    "Check Box3",   # LLC checkbox
}

def fill_form():
    reader = PdfReader(TEMPLATE)
    writer = PdfWriter()
    writer.append(reader)

    # Fill text fields
    for page_num in range(len(writer.pages)):
        writer.update_page_form_field_values(
            writer.pages[page_num],
            FIELD_DATA,
            auto_regenerate=False,
        )

    # Check specific checkboxes
    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot_ref in annots:
            annot = annot_ref.get_object()
            field_name = annot.get("/T")
            if field_name and str(field_name) in CHECKBOXES_ON:
                annot.update({
                    NameObject("/V"): NameObject("/Yes"),
                    NameObject("/AS"): NameObject("/Yes"),
                })

    writer.write(OUTPUT)
    print(f"Generated: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT):,} bytes")
    print(f"Pages: {len(reader.pages)}")
    print(f"Fields filled: {sum(1 for v in FIELD_DATA.values() if v)}")

if __name__ == '__main__':
    fill_form()
