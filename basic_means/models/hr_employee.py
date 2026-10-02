from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    basic_means_assignment_ids = fields.One2many(
        'basic.means.assignment', 'employee_id', string='Fixed Assets Issuances',
        groups='maintenance.group_equipment_manager')
    basic_means_issued_count = fields.Integer(
        string='Issued Fixed Assets', compute='_compute_basic_means_issued_count',
        groups='maintenance.group_equipment_manager')

    def _compute_basic_means_issued_count(self):
        counts = dict(self.env['basic.means.assignment']._read_group(
            [('employee_id', 'in', self.ids), ('state', '=', 'issued')], ['employee_id'], ['__count']))
        for employee in self:
            employee.basic_means_issued_count = counts.get(employee._origin, 0)

    def action_view_basic_means_assignments(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('basic_means.basic_means_assignment_action')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {
            'default_employee_id': self.id,
            'search_default_filter_issued': 1,
        }
        action['view_mode'] = 'list,kanban,form'
        action['views'] = [(False, 'list'), (False, 'kanban'), (False, 'form')]
        return action
