# Copyright (c) 2023, Nirali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowtime, today, getdate
from frappe.model.workflow import apply_workflow

class GatePass(Document):
	def after_insert(self):
		if self.gatepass_type == "For Interview" or self.gatepass_type == "In-Visitor":
			if self.in_time and self.workflow_state == 'Draft':
				apply_workflow(self, "Approve")

	def on_update(self):
		if self.gatepass_type == "For Interview" or self.gatepass_type == "In-Visitor":
			if self.out_time and self.workflow_state == 'Visitor-In':
				apply_workflow(self, "Approve")
		
		if self.gatepass_type == "Inter-Movement":
			if self.in_time and self.workflow_state == 'Out For Department':
				apply_workflow(self, "In")
		
		if self.gatepass_type == "Out-Personal Work":
			if self.in_time and self.workflow_state == 'Out Confirmed':
				apply_workflow(self, "In Confirm")
		
		if self.gatepass_type == "Out-Office Work":
			if self.in_time and self.workflow_state == 'Out Confirmed':
				apply_workflow(self, "In Confirm")

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