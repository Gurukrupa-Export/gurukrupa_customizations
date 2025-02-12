// Copyright (c) 2023, 8848 Digital LLP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Personal Out Gate Pass', {
	onload(frm) {
		let start = frappe.datetime.month_start(frappe.datetime.get_today())
		let end = frappe.datetime.month_end(frappe.datetime.get_today())
		frm.set_value({"from_date":start,"to_date":end})
	},
	after_save: function(frm) {
		frm.call("get_checkin_details",{"from_log":true})
	}
});