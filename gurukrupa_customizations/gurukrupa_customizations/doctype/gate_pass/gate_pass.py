# Copyright (c) 2023, Nirali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowtime, today, getdate

class GatePass(Document):
	def before_save(self):
		if self.is_new():
			if self.gatepass_type == "In-Visitor":
				self.in_time = nowtime()
				self.out_time = None
			else:
				self.out_time = nowtime()
				self.in_time = None


@frappe.whitelist()
def get_recent_visits(gatepass_type):
	filters = {"gatepass_type":gatepass_type, "visit_date": getdate(today())}
	if gatepass_type == "In-Visitor":
		filters["out_time"] = ['is', "not set"]
	else:
		filters["in_time"] = ['is', "not set"]
		
	data = frappe.db.get_list("Gate Pass", filters=filters,fields="*")
	return frappe.render_template("gurukrupa_customizations/gurukrupa_customizations/doctype/gate_pass/recent_visitors.html", {"data":data})

@frappe.whitelist()
def update_gatepass(docname,type="In",time=None):	#type is gatepass type
	field = "in_time" if type == "Out" else "out_time"
	if not time:
		time = frappe.utils.nowtime()
	frappe.db.set_value("Gate Pass", docname, field, time)
	return 1