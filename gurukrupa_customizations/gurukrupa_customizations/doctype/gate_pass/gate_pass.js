// Copyright (c) 2023, Nirali and contributors
// For license information, please see license.txt

frappe.ui.form.on('Gate Pass', {
	refresh(frm) {
		var field = frm.doc.gatepass_type=="In-Visitor"? "out_time":"in_time"
		if (!frm.doc.__islocal && !frm.doc[field]) {
			frm.add_custom_button(__(frm.doc.gatepass_type=="In-Visitor"? "Out":"In"), function() {
				var dialog = new frappe.ui.Dialog({
					title: __('Update Gate Pass'),
					fields: [{
						fieldname: field,
						label: __('Time'),
						fieldtype: 'Time',
					},
					],
				});
				dialog.show();
				dialog.get_field(field).set_input(frappe.datetime.now_time());
				dialog.set_primary_action(__('Submit'), function () {
					let time = dialog.get_value(field)
					frm.set_value(field, time)
					frm.save()
					dialog.hide()
				});
			}).addClass('btn-primary')
		}
		set_html(frm)
	},
	onload_post_render(frm){
		set_html(frm)
		// if (!frm.doc.com_contact_no) frm.get_field('com_contact_no').setup_country_code_picker()
	},
	employee(frm) {
		if (frm.doc.employee) {
			frappe.db.get_value("Employee",frm.doc.employee, "employee_name", (r)=>{
				frm.set_value("visitor_name", r.employee_name)
			})
		}
	},
	validate(frm) {
		if (frm.doc.com_contact_no) {
			let contact_no = frm.doc.com_contact_no.trim()
			if (contact_no.length < 10) {
				frappe.throw(__("Invalid Company Contact No"));
			}
			frm.set_value("com_contact_no", contact_no)
		}
		if (frm.doc.mobile_no) {
			let contact_no = frm.doc.mobile_no.trim()
			if (contact_no.length < 10) {
				frappe.throw(__("Invalid Mobile No"));
			}
			frm.set_value("mobile_no", contact_no)
		}
	}
})

function set_html(frm) {
	if (!frm.doc.__islocal) {
		frappe.call({ 
			method: "gurukrupa_customizations.gurukrupa_customizations.doctype.gate_pass.gate_pass.get_recent_visits",
			args: { 
				"gatepass_type": frm.doc.gatepass_type,
			}, 
			callback: function (r) { 
				frm.get_field("visits").$wrapper.html(r.message) 
			} 
		})
	}
	else {
		frm.get_field("visits").$wrapper.html("")
	}
}