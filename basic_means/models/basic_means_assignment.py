from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BasicMeansAssignment(models.Model):
    _name = 'basic.means.assignment'
    _description = 'Fixed Asset Issuance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_issue desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Number', required=True, readonly=True, copy=False, default='/', index='trigram')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    equipment_id = fields.Many2one(
        'maintenance.equipment', string='Fixed Asset', required=True, index=True,
        tracking=True, check_company=True, ondelete='restrict')
    model = fields.Char(related='equipment_id.model')
    serial_no = fields.Char(related='equipment_id.serial_no')
    category_id = fields.Many2one(related='equipment_id.category_id', store=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        tracking=True, check_company=True, ondelete='restrict')
    department_id = fields.Many2one(
        'hr.department', string='Department', compute='_compute_department_id',
        store=True, readonly=False)
    job_title = fields.Char(related='employee_id.job_title')
    user_id = fields.Many2one(
        'res.users', string='Responsible', default=lambda self: self.env.user,
        domain="[('share', '=', False)]", tracking=True,
        help='Person who hands the fixed asset over to the employee.')
    date_issue = fields.Date(
        string='Issue Date', required=True, default=fields.Date.context_today, tracking=True)
    date_return = fields.Date(string='Return Date', copy=False, tracking=True)
    days_count = fields.Integer(
        string='Days in Use', compute='_compute_days_count',
        help='Number of days from the issue date to the return date (or to today if not returned yet).')
    state = fields.Selection(
        [('draft', 'Draft'), ('issued', 'Issued'), ('returned', 'Returned')],
        string='Status', required=True, default='draft', copy=False, tracking=True, index=True)
    note = fields.Html(string='Note')
    color = fields.Integer(string='Color Index')

    # Guarantees on the database level (also under concurrency) that one fixed asset
    # can not be issued to several employees at the same time.
    _equipment_issued_unique = models.UniqueIndex(
        "(equipment_id) WHERE state = 'issued'",
        "This fixed asset is already issued to an employee. Return it first.",
    )
    _date_return_check = models.Constraint(
        'CHECK(date_return IS NULL OR date_return >= date_issue)',
        "The return date can not be earlier than the issue date.",
    )

    @api.depends('employee_id')
    def _compute_department_id(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id

    @api.depends('date_issue', 'date_return', 'state')
    @api.depends_context('tz')
    def _compute_days_count(self):
        today = fields.Date.context_today(self)
        for rec in self:
            end = rec.date_return or today
            rec.days_count = max((end - rec.date_issue).days, 0) if rec.date_issue else 0

    @api.constrains('equipment_id', 'state', 'date_issue', 'date_return')
    def _check_equipment_availability(self):
        """ Periods of use of the same fixed asset must not overlap. """
        for rec in self.filtered(lambda r: r.state in ('issued', 'returned')):
            domain = [
                ('id', '!=', rec.id),
                ('equipment_id', '=', rec.equipment_id.id),
                ('state', 'in', ('issued', 'returned')),
                '|', ('date_return', '=', False), ('date_return', '>', rec.date_issue),
            ]
            if rec.date_return:
                domain.append(('date_issue', '<', rec.date_return))
            conflict = self.search(domain, limit=1)
            if conflict:
                raise ValidationError(self.env._(
                    "The fixed asset \"%(equipment)s\" is already issued to %(employee)s "
                    "for this period (%(number)s, from %(date)s).",
                    equipment=rec.equipment_id.display_name,
                    employee=conflict.employee_id.name,
                    number=conflict.name,
                    date=conflict.date_issue,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id
                ).next_by_code('basic.means.assignment') or '/'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(self.env._("Only draft issuances can be deleted. Issued or returned "
                                       "fixed assets are kept in the history."))

    # ------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------

    def action_issue(self):
        """ Issue the fixed asset: assign it to the employee. """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(self.env._("Only draft issuances can be issued."))
            if rec.equipment_id.basic_means_assignment_id:
                current = rec.equipment_id.basic_means_assignment_id
                raise UserError(self.env._(
                    "The fixed asset \"%(equipment)s\" is already issued to %(employee)s (%(number)s). "
                    "Return it to the warehouse first.",
                    equipment=rec.equipment_id.display_name,
                    employee=current.employee_id.name,
                    number=current.name,
                ))
            rec.write({'state': 'issued', 'date_return': False})
            # standard hr_maintenance fields: who uses the equipment right now
            rec.equipment_id.write({
                'equipment_assign_to': 'employee',
                'employee_id': rec.employee_id.id,
                'assign_date': rec.date_issue,
            })
            rec.equipment_id.message_post(body=Markup(self.env._("Issued to %(employee)s, act %(link)s")) % {
                'employee': rec.employee_id.name,
                'link': rec._get_html_link(),
            })
        return True

    def action_return(self):
        """ Return the fixed asset from the employee to the warehouse. """
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'issued':
                raise UserError(self.env._("Only issued fixed assets can be returned."))
            rec.write({
                'state': 'returned',
                'date_return': max(rec.date_return or today, rec.date_issue),
            })
            equipment = rec.equipment_id
            if equipment.employee_id == rec.employee_id:
                equipment.write({'employee_id': False, 'assign_date': False})
            equipment.message_post(body=Markup(self.env._("Returned to the warehouse from %(employee)s, act %(link)s")) % {
                'employee': rec.employee_id.name,
                'link': rec._get_html_link(),
            })
        return True

    def action_print_act(self):
        return self.env.ref('basic_means.action_report_basic_means_act').report_action(self)
