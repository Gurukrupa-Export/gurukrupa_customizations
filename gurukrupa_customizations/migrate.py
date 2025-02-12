import json
import os


def after_migrate():
	create_custom_fields()


def create_custom_fields():
	CUSTOM_FIELDS = {}
	print("Creating/Updating Custom Fields....")
	path = os.path.join(os.path.dirname(__file__), "gurukrupa_customizations/custom_fields")
	for file in os.listdir(path):
		with open(os.path.join(path, file), "r") as f:
			CUSTOM_FIELDS.update(json.load(f))
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(CUSTOM_FIELDS)


def create_property_setter():
	from frappe import make_property_setter

	print("Creating/Updating Property Setter....")
	path = os.path.join(os.path.dirname(__file__), "gurukrupa_customizations/property_setter")
	for file in os.listdir(path):
		with open(os.path.join(path, file), "r") as f:
			args = json.load(f)
			make_property_setter(args, is_system_generated=False)
