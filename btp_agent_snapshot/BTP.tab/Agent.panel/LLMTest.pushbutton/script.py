#! python3

import os
from pyrevit import revit, DB
from System.Windows import MessageBox
from openai import OpenAI

print("=== BTP LLM ROUND TRIP ===")

# 1. Get Revit document
doc = revit.doc

# 2. Collect Revit categories
collector = DB.FilteredElementCollector(doc).WhereElementIsNotElementType()

categories = set()

for element in collector:
    if element.Category:
        categories.add(element.Category.Name)

category_list = sorted(list(categories))

print("Categories collected:", len(category_list))

# 3. Get API key
api_key = os.getenv("BTP_API")

# 4. Create OpenAI client
client = OpenAI(api_key=api_key)

# 5. Send Revit data to LLM
messages = [
    {
        "role": "user",
        "content": (
            "These are the Revit categories in my model:\n\n"
            "{}\n\n"
            "Which of these categories are structural? "
            "Give a short answer."
        ).format(category_list)
    }
]

print("Sending Revit data to LLM...")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages
)

# 6. Receive LLM answer
answer = response.choices[0].message.content

print("LLM response received.")

# 7. Display answer inside Revit
MessageBox.Show(answer, "BTP BIM Assistant")

print("=== ROUND TRIP SUCCESS ===")