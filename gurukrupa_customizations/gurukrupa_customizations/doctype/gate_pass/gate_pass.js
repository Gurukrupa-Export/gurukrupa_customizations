// Copyright (c) 2023, Nirali and contributors
// For license information, please see license.txt

frappe.ui.form.on('Gate Pass', {
	setup(frm){
		
	},
	refresh(frm) {	
		let condition = ["In-Visitor", "For Interview"].includes(frm.doc.gatepass_type);
		let field = condition ? "out_time" : "in_time";
		let btn_label = condition ? "Out" : "In";

		if (frm.is_new()) {
			if (frm.doc.gatepass_type === 'Inter-Movement'){
				frm.set_value('inter_in_time', '');
				frm.set_value('inter_out_time', '');
			}
		}
		
		// Auto defaults for new docs
		if (frm.is_new()) {
			if (["In-Visitor", "For Interview"].includes(frm.doc.gatepass_type)) {
				frm.set_value('in_time', frappe.datetime.now_time());
				frm.set_value('out_time', '');
				frm.set_value('inter_in_time', '');
				frm.set_value('inter_out_time', '');
			} else {
				frm.set_value('out_time', frappe.datetime.now_time());
				frm.set_value('in_time', '');
				frm.set_value('inter_in_time', '');
				frm.set_value('inter_out_time', '');
			}

			
			// remove custom button only if form is not new
			// frm.remove_custom_button(btn_label);
		}

		// Clear existing buttons on refresh
		frm.clear_custom_buttons();

		// Show button for original conditions
		if (!frm.doc[field] && ["In-Visitor", "For Interview"].includes(frm.doc.gatepass_type)) {
			add_gatepass_button(frm, field, btn_label);
		}

		// remove custom button only if form is not new
		if (frm.is_new()) { 
			console.log(btn_label);
			frm.remove_custom_button(btn_label);
		}

		const allowed_types = ['Out-Personal Work', 'Out-Office Work'];
		const allowed_states = ['Out Confirmed'];

		if (allowed_types.includes(frm.doc.gatepass_type) && allowed_states.includes(frm.doc.workflow_state) && !frm.doc.in_time) {
			add_gatepass_button(frm, "in_time", "In");
		}
		

		// Hide/Show action buttons for 'In-Visitor' type
		const is_security = frappe.user.has_role("GK Security");
		if (
			(frm.doc.gatepass_type === "In-Visitor" && is_security) || 
			(frm.doc.gatepass_type === "For Interview" && is_security) || 
			(frm.doc.gatepass_type === 'Out-Personal Work' && frm.doc.workflow_state === 'Out Confirmed') 
			// || (frm.doc.gatepass_type === 'Inter-Movement' && (frm.doc.workflow_state === 'Send to Floor Security')) 
		
		) {
			frm.page.wrapper.find('.actions-btn-group').hide(); 
		} else {
			frm.page.wrapper.find('.actions-btn-group').show();
		}
 
	},
	after_workflow_action(frm) {
        setTimeout(() => {
            if(frm.doc.gatepass_type === 'Inter-Movement' && frm.doc.workflow_state === 'Out For Department' && !frm.doc.in_time){
				frm.set_value('out_time', frappe.datetime.now_time());
				frm.save()
			}
            if(frm.doc.gatepass_type === 'Inter-Movement' && frm.doc.workflow_state === 'In For Department'){
				frm.set_value('inter_in_time', frappe.datetime.now_time());
				frm.save()
			}
			if(frm.doc.gatepass_type === 'Inter-Movement' && frm.doc.workflow_state === 'Send to Floor Security' && frm.doc.inter_in_time){
				frm.set_value('inter_out_time', frappe.datetime.now_time());
				frm.save()
			}
			if(frm.doc.gatepass_type === 'Inter-Movement' && frm.doc.workflow_state === 'Returned To Department' && !frm.doc.in_time){
				frm.set_value('in_time', frappe.datetime.now_time());
				frm.save()
			}
        }, 100);
    },
    gatepass_type(frm) {
        if (["In-Visitor", "For Interview"].includes(frm.doc.gatepass_type)) {
            frm.set_value('in_time', frappe.datetime.now_time());
            frm.set_value('out_time', '');
        } else {
            frm.set_value('out_time', frappe.datetime.now_time());
            frm.set_value('in_time', '');
        }
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

function add_gatepass_button(frm, field, label) {
    frm.add_custom_button(__(label), function () {
        let dialog = new frappe.ui.Dialog({
            title: __('Update Gate Pass'),
            fields: [{
                fieldname: field,
                label: __('Time'),
                fieldtype: 'Time',
                default: frappe.datetime.now_time()
            }]
        });

        dialog.set_primary_action(__('Submit'), function () {
            let time = dialog.get_value(field);
            frm.set_value(field, time);
            frm.save().then(() => {
                frm.reload_doc();
            });
            dialog.hide();
        });

        dialog.show();
    }).addClass('btn-primary');
}