frappe.ui.form.on('Cost Center', {
	setup(frm) {
		frm.set_query("inter_unit_account", function() {
		    return {
		        filters: {
		            "Company": frm.doc.company
		        }
		    }
		})
	}
})