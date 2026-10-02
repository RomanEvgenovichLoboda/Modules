from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestBasicMeansAssignment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env['basic.means.assignment'])
        cls.equipment = cls.env['maintenance.equipment'].create({
            'name': 'Test Laptop',
            'model': 'ThinkPad T14',
            'serial_no': 'SN-TEST-001',
        })
        cls.employee_1 = cls.env['hr.employee'].create({'name': 'Employee One'})
        cls.employee_2 = cls.env['hr.employee'].create({'name': 'Employee Two'})

    def _create(self, employee, **vals):
        return self.env['basic.means.assignment'].create({
            'equipment_id': self.equipment.id,
            'employee_id': employee.id,
            **vals,
        })

    def test_sequence_and_days_count(self):
        assignment = self._create(self.employee_1, date_issue=self.today - timedelta(days=12))
        self.assertNotEqual(assignment.name, '/')
        self.assertEqual(assignment.model, 'ThinkPad T14')
        self.assertEqual(assignment.days_count, 12)
        assignment.date_return = self.today - timedelta(days=2)
        self.assertEqual(assignment.days_count, 10)

    def test_issue_and_return(self):
        assignment = self._create(self.employee_1, date_issue=self.today - timedelta(days=5))
        assignment.action_issue()
        self.assertEqual(assignment.state, 'issued')
        self.assertEqual(self.equipment.employee_id, self.employee_1)
        self.assertEqual(self.equipment.assign_date, assignment.date_issue)
        self.assertEqual(self.equipment.basic_means_state, 'issued')
        self.assertEqual(self.equipment.basic_means_assignment_id, assignment)

        assignment.action_return()
        self.assertEqual(assignment.state, 'returned')
        self.assertEqual(assignment.date_return, self.today)
        self.assertEqual(assignment.days_count, 5)
        self.assertFalse(self.equipment.employee_id)
        self.assertEqual(self.equipment.basic_means_state, 'in_stock')
        self.assertFalse(self.equipment.basic_means_assignment_id)

        # the same fixed asset can be issued again after the return
        assignment_2 = self._create(self.employee_2)
        assignment_2.action_issue()
        self.assertEqual(self.equipment.employee_id, self.employee_2)
        self.assertEqual(self.equipment.basic_means_assignment_count, 2)

    def test_cannot_issue_twice(self):
        self._create(self.employee_1).action_issue()
        assignment_2 = self._create(self.employee_2)
        with self.assertRaises(UserError):
            assignment_2.action_issue()

    def test_database_prevents_double_issue(self):
        """ Even bypassing the ORM checks, the partial unique index forbids a second issue. """
        self._create(self.employee_1).action_issue()
        assignment_2 = self._create(self.employee_2)
        self.env.flush_all()
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.env.cr.execute(
                "UPDATE basic_means_assignment SET state = 'issued' WHERE id = %s", [assignment_2.id])

    def test_periods_cannot_overlap(self):
        self._create(
            self.employee_1, state='returned',
            date_issue=self.today - timedelta(days=30), date_return=self.today - timedelta(days=10))
        with self.assertRaises(ValidationError):
            self._create(self.employee_2, date_issue=self.today - timedelta(days=20)).action_issue()
        # issuing right after the return is allowed
        self._create(self.employee_2, date_issue=self.today - timedelta(days=10)).action_issue()

    def test_return_date_before_issue_date(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self._create(self.employee_1, date_issue=self.today, date_return=self.today - timedelta(days=1))

    def test_unlink_only_draft(self):
        draft = self._create(self.employee_1)
        issued = self._create(self.employee_2, date_issue=self.today)
        draft.unlink()
        issued.action_issue()
        with self.assertRaises(UserError):
            issued.unlink()

    def test_equipment_buttons(self):
        action = self.equipment.action_basic_means_issue()
        self.assertEqual(action['context']['default_equipment_id'], self.equipment.id)
        with Form(self.env['basic.means.assignment'].with_context(action['context'])) as form:
            form.employee_id = self.employee_1
        form.record.action_issue()
        self.equipment.action_basic_means_return()
        self.assertEqual(form.record.state, 'returned')
        self.assertEqual(self.employee_1.basic_means_issued_count, 0)

    def test_report(self):
        assignment = self._create(self.employee_1)
        assignment.action_issue()
        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            'basic_means.action_report_basic_means_act', assignment.ids)
        self.assertEqual(report_type, 'html')
        self.assertIn(b'Employee One', html)
        self.assertIn(b'SN-TEST-001', html)
