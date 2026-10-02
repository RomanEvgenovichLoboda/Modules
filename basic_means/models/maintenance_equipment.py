from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    basic_means_assignment_ids = fields.One2many(
        'basic.means.assignment', 'equipment_id', string='Issuance History')
    basic_means_assignment_count = fields.Integer(
        string='Issuances', compute='_compute_basic_means_assignment_count')
    basic_means_assignment_id = fields.Many2one(
        'basic.means.assignment', string='Current Issuance',
        compute='_compute_basic_means_assignment_id', store=True, index='btree_not_null')
    basic_means_state = fields.Selection(
        [('in_stock', 'In Stock'), ('issued', 'Issued')], string='Issuance Status',
        compute='_compute_basic_means_assignment_id', store=True)

    def _compute_basic_means_assignment_count(self):
        counts = dict(self.env['basic.means.assignment']._read_group(
            [('equipment_id', 'in', self.ids)], ['equipment_id'], ['__count']))
        for equipment in self:
            equipment.basic_means_assignment_count = counts.get(equipment._origin, 0)

    @api.depends('basic_means_assignment_ids.state')
    def _compute_basic_means_assignment_id(self):
        for equipment in self:
            current = equipment.basic_means_assignment_ids.filtered(lambda a: a.state == 'issued')[:1]
            equipment.basic_means_assignment_id = current
            equipment.basic_means_state = 'issued' if current else 'in_stock'

    def _get_basic_means_action(self):
        action = self.env['ir.actions.actions']._for_xml_id('basic_means.basic_means_assignment_action')
        action['context'] = {
            'default_equipment_id': self.id,
            'default_company_id': self.company_id.id or self.env.company.id,
        }
        return action

    def action_view_basic_means_assignments(self):
        self.ensure_one()
        action = self._get_basic_means_action()
        action['domain'] = [('equipment_id', '=', self.id)]
        action['view_mode'] = 'list,kanban,form'
        action['views'] = [(False, 'list'), (False, 'kanban'), (False, 'form')]
        return action

    def action_basic_means_issue(self):
        """ Open a new issuance for this fixed asset. """
        self.ensure_one()
        action = self._get_basic_means_action()
        action.update(view_mode='form', views=[(False, 'form')], target='current')
        return action

    def action_basic_means_return(self):
        return self.basic_means_assignment_id.action_return()
