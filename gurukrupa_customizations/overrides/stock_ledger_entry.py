import frappe


def after_submit(doc, method=None):
    if doc.voucher_type and doc.voucher_no and doc.voucher_detail_no and doc.batch_no:
        child_doctype = doc.voucher_type + " Item"
        if doc.voucher_type == "Stock Entry":
            child_doctype = "Stock Entry Detail"

        data = frappe.get_all(child_doctype, 
            filters={"parent": doc.voucher_no, "batch_no": doc.batch_no, "name": doc.voucher_detail_no},
            fields = ["customer", "inventory_type"],
            limit=1
        )

        if data:
            batch_doc = frappe.get_doc("Batch", doc.batch_no)
            batch_doc.customer = data[0].customer
            batch_doc.inventory_type = data[0].inventory_type
            batch_doc.save()