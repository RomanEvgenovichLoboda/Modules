{
    'name': 'Fixed Assets Issuance',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Issue fixed assets (equipment) to employees, return them to the warehouse, history and issuance act',
    'description': """
Fixed Assets Issuance (Основні засоби)
======================================

Built on top of the standard *Maintenance* equipment (``maintenance.equipment``)
and *Employees* (``hr.employee``) via the standard bridge ``hr_maintenance``.

* Issuance record: fixed asset (model, serial number, category) + employee + issue date,
  with the number of days in use computed from the issue date.
* Issuance history: the same fixed asset can not be issued to more than one employee
  at the same time (Python constraint + partial unique index in the database).
* "Issue" (assign the fixed asset to the employee) and "Return" (return it to the
  warehouse) buttons, both on the issuance and on the equipment form.
* Kanban of the issuance history grouped by fixed asset or by employee.
* PDF report "Fixed Asset Issuance Act" for a specific employee and fixed asset.
""",
    'author': 'Roman Loboda',
    'depends': ['hr_maintenance'],
    'data': [
        'security/basic_means_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'report/basic_means_assignment_report.xml',
        'views/basic_means_assignment_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/hr_employee_views.xml',
        'views/basic_means_menus.xml',
    ],
    'demo': [
        'demo/basic_means_demo.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
