# -*- coding: utf-8 -*-
#
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011-2012 Domsense s.r.l. (<http://www.domsense.com>).
#    Copyright (C) 2012-15 Agile Business Group sagl (<http://www.agilebg.com>)
#    Copyright (C) 2015 Associazione Odoo Italia
#    (<http://www.odoo-italia.org>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import math
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp
from odoo.tools import float_is_zero


class AccountVatPeriodEndStatement(models.Model):

    @api.multi
    def _compute_authority_vat_amount(self):
        for statement in self:
            debit_vat_amount = 0.0
            credit_vat_amount = 0.0
            generic_vat_amount = 0.0
            for debit_line in statement.debit_vat_account_line_ids:
                debit_vat_amount += debit_line.amount
            for credit_line in statement.credit_vat_account_line_ids:
                credit_vat_amount += credit_line.amount
            for generic_line in statement.generic_vat_account_line_ids:
                generic_vat_amount += generic_line.amount
            authority_amount = (
                debit_vat_amount - credit_vat_amount - generic_vat_amount -
                statement.previous_credit_vat_amount +
                statement.previous_debit_vat_amount)
            statement.authority_vat_amount = authority_amount

    @api.multi
    def _compute_payable_vat_amount(self):
        for statement in self:
            debit_vat_amount = 0.0
            for debit_line in statement.debit_vat_account_line_ids:
                debit_vat_amount += debit_line.amount
            statement.payable_vat_amount = debit_vat_amount
        return res

    @api.multi
    def _compute_deductible_vat_amount(self):
        for statement in self:
            credit_vat_amount = 0.0
            for credit_line in statement.credit_vat_account_line_ids:
                credit_vat_amount += credit_line.amount
            statement.deductible_vat_amount = credit_vat_amount

    @api.multi
    @api.depends(
        'state',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        precision = self.env.user.company_id.currency_id.decimal_places
        for statement in self:
            residual = 0.0
            if not statement.move_id:
                statement.residual = 0.0
                statement.reconciled = False
                return
            for line in statement.move_id.line_ids:
                if line.account_id.internal_type in ('receivable', 'payable'):
                    residual += line.amount_residual
            statement.residual = abs(residual)
            if float_is_zero(statement.residual, precision_digits=precision):
                statement.reconciled = True
            else:
                statement.reconciled = False

    @api.depends('move_id.line_ids.amount_residual')
    @api.multi
    def _compute_lines(self):
        for statement in self:
            payment_lines = []
            for line in statement.move_id.line_ids:
                payment_lines.extend(filter(None, [
                    rp.credit_move_id.id for rp in line.matched_credit_ids
                ]))
                payment_lines.extend(filter(None, [
                    rp.debit_move_id.id for rp in line.matched_debit_ids
                ]))
            self.payment_ids = self.env['account.move.line'].browse(
                list(set(payment_lines)))

    @api.model
    def _get_default_interest(self):
        company = self.env.user.company_id
        return company.of_account_end_vat_statement_interest

    @api.model
    def _get_default_interest_percent(self):
        company = self.env.user.company_id
        if not company.of_account_end_vat_statement_interest:
            return 0
        return company.of_account_end_vat_statement_interest_percent

    _name = "account.vat.period.end.statement"
    _rec_name = 'date'
    debit_vat_account_line_ids = fields.One2many(
        'statement.debit.account.line', 'statement_id', 'Debit VAT',
        help='The accounts containing the debit VAT amount to write-off',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]
        }
    )
    credit_vat_account_line_ids = fields.One2many(
        'statement.credit.account.line', 'statement_id', 'Credit VAT',
        help='The accounts containing the credit VAT amount to write-off',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]
        })
    previous_credit_vat_account_id = fields.Many2one(
        'account.account', 'Previous Credits VAT',
        help='Credit VAT from previous periods',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]
        })
    previous_credit_vat_amount = fields.Float(
        'Previous Credits VAT Amount',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]
        }, digits=dp.get_precision('Account'))
    previous_debit_vat_account_id = fields.Many2one(
        'account.account', 'Previous Debits VAT',
        help='Debit VAT from previous periods',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]
        })
    previous_debit_vat_amount = fields.Float(
        'Previous Debits VAT Amount',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]
        }, digits=dp.get_precision('Account'))
    generic_vat_account_line_ids = fields.One2many(
        'statement.generic.account.line', 'statement_id',
        'Other VAT Credits / Debits or Tax Compensations',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]})
    authority_partner_id = fields.Many2one(
        'res.partner', 'Tax Authority Partner',
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]})
    authority_vat_account_id = fields.Many2one(
        'account.account', 'Tax Authority VAT Account', required=True,
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]})
    authority_vat_amount = fields.Float(
        'Authority VAT Amount', compute="_compute_authority_vat_amount",
        digits=dp.get_precision('Account'))
    payable_vat_amount = fields.Float(
        'Payable VAT Amount', compute="_compute_payable_vat_amount",
        digits=dp.get_precision('Account'))
    deductible_vat_amount = fields.Float(
        'Deductible VAT Amount', compute="_compute_deductible_vat_amount",
        digits=dp.get_precision('Account'))
    journal_id = fields.Many2one(
        'account.journal', 'Journal', required=True,
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]})
    date = fields.Date(
        'Date', required=True,
        states={
            'confirmed': [('readonly', True)],
            'paid': [('readonly', True)],
            'draft': [('readonly', False)]},
        default=fields.Date.context_today)
    move_id = fields.Many2one(
        'account.move', 'VAT statement move', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
    ], 'State', readonly=True, default='draft')
    payment_term_id = fields.Many2one(
        'account.payment.term', 'Payment Term',
        states={
            'confirmed': [
                ('readonly', True)], 'paid': [('readonly', True)],
            'draft': [('readonly', False)]})
    reconciled = fields.Boolean(
        'Paid/Reconciled', compute="_compute_residual",
        help="It indicates that the statement has been paid and the "
             "journal entry of the statement has been reconciled with "
             "one or several journal entries of payment.",
        store=True, readonly=True
    )
    residual = fields.Float(string='Amount Due',
        compute='_compute_residual', store=True, help="Remaining amount due.",
        digits=dp.get_precision('Account'))
    payment_ids = fields.Many2many(
        'account.move.line', string='Payments', compute="_compute_lines",
        store=True)
    date_range_ids = fields.One2many(
        'date.range', 'vat_statement_id', 'Periods')
    interest = fields.Boolean(
        'Compute Interest', default=_get_default_interest)
    interest_percent = fields.Float(
        'Interest - Percent', default=_get_default_interest_percent)
    fiscal_page_base = fields.Integer(
        'Last printed page', required=True, default=1)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get(
            'account.invoice'))

    @api.multi
    def unlink(self):
        for statement in self:
            if statement.state == 'confirmed' or statement.state == 'paid':
                raise UserError(
                    _('You cannot delete a confirmed or paid statement'))
        res = super(AccountVatPeriodEndStatement, self).unlink()
        return res

    @api.multi
    def _write(self, vals):
        pre_not_reconciled = self.filtered(
            lambda statement: not statement.reconciled)
        pre_reconciled = self - pre_not_reconciled
        res = super(AccountVatPeriodEndStatement, self)._write(vals)
        reconciled = self.filtered(lambda statement: statement.reconciled)
        not_reconciled = self - reconciled
        (reconciled & pre_reconciled).filtered(
            lambda statement: statement.state == 'confirmed'
        ).statement_paid()
        (not_reconciled & pre_not_reconciled).filtered(
            lambda statement: statement.state == 'paid'
        ).statement_confirmed()
        return res

    @api.multi
    def statement_draft(self):
        for statement in self:
            if statement.move_id:
                statement.move_id.unlink()
            statement.state = 'draft'

    @api.multi
    def statement_paid(self):
        for statement in self:
            statement.state = 'paid'

    @api.multi
    def statement_confirmed(self):
        for statement in self:
            statement.state = 'confirmed'

    @api.multi
    def create_move(self):
        move_obj = self.env['account.move']
        term_obj = self.env['account.payment.term']
        line_obj = self.env['account.move.line']
        period_obj = self.env['account.period']
        for statement in self:
            move_data = {
                'name': _('VAT statement') + ' - ' + statement.date,
                'date': statement.date,
                'journal_id': statement.journal_id.id,
            }
            move_id = move_obj.create(move_data)
            statement.write({'move_id': move_id})

            for debit_line in statement.debit_vat_account_line_ids:
                if debit_line.amount != 0.0:
                    debit_vat_data = {
                        'name': _('Debit VAT'),
                        'account_id': debit_line.account_id.id,
                        'move_id': move_id,
                        'journal_id': statement.journal_id.id,
                        'debit': 0.0,
                        'credit': 0.0,
                        'date': statement.date,
                    }

                    if debit_line.amount > 0:
                        debit_vat_data['debit'] = math.fabs(debit_line.amount)
                    else:
                        debit_vat_data['credit'] = math.fabs(debit_line.amount)
                    line_obj.create(debit_vat_data)

            for credit_line in statement.credit_vat_account_line_ids:
                if credit_line.amount != 0.0:
                    credit_vat_data = {
                        'name': _('Credit VAT'),
                        'account_id': credit_line.account_id.id,
                        'move_id': move_id,
                        'journal_id': statement.journal_id.id,
                        'debit': 0.0,
                        'credit': 0.0,
                        'date': statement.date,
                    }
                    if credit_line.amount < 0:
                        credit_vat_data['debit'] = math.fabs(
                            credit_line.amount)
                    else:
                        credit_vat_data['credit'] = math.fabs(
                            credit_line.amount)
                    line_obj.create(credit_vat_data)

            if statement.previous_credit_vat_amount:
                previous_credit_vat_data = {
                    'name': _('Previous Credits VAT'),
                    'account_id': statement.previous_credit_vat_account_id.id,
                    'move_id': move_id,
                    'journal_id': statement.journal_id.id,
                    'debit': 0.0,
                    'credit': 0.0,
                    'date': statement.date,
                }
                if statement.previous_credit_vat_amount < 0:
                    previous_credit_vat_data['debit'] = math.fabs(
                        statement.previous_credit_vat_amount)
                else:
                    previous_credit_vat_data['credit'] = math.fabs(
                        statement.previous_credit_vat_amount)
                line_obj.create(previous_credit_vat_data)

            if statement.previous_debit_vat_amount:
                previous_debit_vat_data = {
                    'name': _('Previous Debits VAT'),
                    'account_id': statement.previous_debit_vat_account_id.id,
                    'move_id': move_id,
                    'journal_id': statement.journal_id.id,
                    'debit': 0.0,
                    'credit': 0.0,
                    'date': statement.date,
                }
                if statement.previous_debit_vat_amount > 0:
                    previous_debit_vat_data['debit'] = math.fabs(
                        statement.previous_debit_vat_amount)
                else:
                    previous_debit_vat_data['credit'] = math.fabs(
                        statement.previous_debit_vat_amount)
                line_obj.create(previous_debit_vat_data)

            for generic_line in statement.generic_vat_account_line_ids:
                generic_vat_data = {
                    'name': _('Other VAT Credits / Debits'),
                    'account_id': generic_line.account_id.id,
                    'move_id': move_id,
                    'journal_id': statement.journal_id.id,
                    'debit': 0.0,
                    'credit': 0.0,
                    'date': statement.date,
                }
                if generic_line.amount < 0:
                    generic_vat_data['debit'] = math.fabs(generic_line.amount)
                else:
                    generic_vat_data['credit'] = math.fabs(generic_line.amount)
                line_obj.create(generic_vat_data)

            end_debit_vat_data = {
                'name': _('Tax Authority VAT'),
                'account_id': statement.authority_vat_account_id.id,
                'partner_id': statement.authority_partner_id.id,
                'move_id': move_id,
                'journal_id': statement.journal_id.id,
                'date': statement.date,
            }
            if statement.authority_vat_amount > 0:
                end_debit_vat_data['debit'] = 0.0
                end_debit_vat_data['credit'] = math.fabs(
                    statement.authority_vat_amount)
                if statement.payment_term_id:
                    due_list = statement.payment_term_id.compute(statement.authority_vat_amount, statement.date)[0]
                    for term in due_list:
                        current_line = end_debit_vat_data
                        current_line['credit'] = term[1]
                        current_line['date_maturity'] = term[0]
                        line_obj.create(current_line)
                else:
                    line_obj.create(end_debit_vat_data)
            elif statement.authority_vat_amount < 0:
                end_debit_vat_data['debit'] = math.fabs(
                    statement.authority_vat_amount)
                end_debit_vat_data['credit'] = 0.0
                line_obj.create(end_debit_vat_data)

            statement.state = 'confirmed'

        return True

    @api.multi
    def compute_amounts(self):
        statement_generic_account_line_model = self.env[
            'statement.generic.account.line']
        decimal_precision_obj = self.env['decimal.precision']
        debit_line_model = self.env['statement.debit.account.line']
        credit_line_model = self.env['statement.credit.account.line']
        for statement in self:
            statement.previous_debit_vat_amount = 0.0
            prev_statements = self.search(
                [('date', '<', statement.date)], order='date desc')
            if prev_statements:
                prev_statement = prev_statements[0]
                if (
                    prev_statement.residual > 0 and
                    prev_statement.authority_vat_amount > 0
                ):
                    statement.write(
                        {'previous_debit_vat_amount': prev_statement.residual})
                elif prev_statement.authority_vat_amount < 0:
                    statement.write(
                        {'previous_credit_vat_amount': (
                            - prev_statement.authority_vat_amount)})

            credit_line_ids = []
            debit_line_ids = []
            tax_model = self.env['account.tax.code']
            debit_taxes = tax_model.search([
                ('vat_statement_account_id', '!=', False),
                ('type_tax_use', '=', 'sale'),
            ])
            for debit_tax in debit_taxes:
                total = 0.0
                for period in statement.date_range_ids:
                    total += tax_model.with_context({
                        'from_date': period.date_start,
                        'to_date': period.date_end,
                    }).browse(debit_tax.id).balance
                debit_line_ids.append({
                    'account_id': debit_tax.vat_statement_account_id.id,
                    'tax_id': debit_tax.id,
                    'amount': total * debit_tax.vat_statement_sign,
                })

            credit_taxes = tax_model.search(cr, uid, [
                ('vat_statement_account_id', '!=', False),
                ('type_tax_use', '=', 'purchase'),
            ])
            for credit_tax in credit_taxes:
                total = 0.0
                for period in statement.date_range_ids:
                    total += tax_model.with_context({
                        'from_date': period.date_start,
                        'to_date': period.date_end,
                    }).browse(credit_tax.id).balance
                credit_line_ids.append({
                    'account_id': credit_tax.vat_statement_account_id.id,
                    'tax_id': credit_tax.id,
                    'amount': total * credit_tax.vat_statement_sign,
                })

            for debit_line in statement.debit_vat_account_line_ids:
                debit_line.unlink()
            for credit_line in statement.credit_vat_account_line_ids:
                credit_line.unlink()
            for debit_vals in debit_line_ids:
                debit_vals.update({'statement_id': statement.id})
                debit_line_model.create(debit_vals)
            for credit_vals in credit_line_ids:
                credit_vals.update({'statement_id': statement.id})
                credit_line_model.create(credit_vals)

            interest_amount = 0.0
            # if exits Delete line with interest
            acc_id = self.get_account_interest(cr, uid, ids, context).id
            domain = [
                ('account_id', '=', acc_id),
                ('statement_id', '=', statement.id),
                ]
            lines = statement_generic_account_line_model.search(domain)
            if lines:
                lines.unlink()

            # Compute interest
            if statement.interest and statement.authority_vat_amount > 0:
                interest_amount = (-1 * round(
                    statement.authority_vat_amount *
                    (float(statement.interest_percent) / 100),
                    decimal_precision_obj.precision_get('Account')))
            # Add line with interest
            if interest_amount:
                val = {
                    'statement_id': statement.id,
                    'account_id': acc_id,
                    'amount': interest_amount,
                    }
                statement_generic_account_line_model.create(val)
        return True

    @api.onchange('authority_partner_id')
    def on_change_partner_id(self):
        self.authority_vat_account_id = (
            self.authority_partner_id.property_account_payable_id.id)

    @api.onchange('interest')
    def onchange_interest(self):
        company = self.env.user.company_id
        self.interest_percent = (
            company.of_account_end_vat_statement_interest_percent)

    @api.multi
    def get_account_interest(self):
        company = self.env.user.company_id
        if (
            company.of_account_end_vat_statement_interest or
            any([s.interest for s in self])
        ):
            if not company.of_account_end_vat_statement_interest_account_id:
                raise UserError(
                    _("The account for vat interest must be configurated"))

        return company.of_account_end_vat_statement_interest_account_id


class StatementDebitAccountLine(models.Model):
    _name = 'statement.debit.account.line'
    account_id = fields.Many2one(
        'account.account', 'Account', required=True
    )
    tax_id = fields.Many2one(
        'account.tax', 'Tax', required=True
    )
    statement_id = fields.Many2one(
        'account.vat.period.end.statement', 'VAT statement'
    )
    amount = fields.Float(
        'Amount', required=True, digits=dp.get_precision('Account')
    )


class StatementCreditAccountLine(models.Model):
    _name = 'statement.credit.account.line'
    account_id = fields.Many2one(
        'account.account', 'Account', required=True
    )
    tax_id = fields.Many2one(
        'account.tax', 'Tax', required=True
    )
    statement_id = fields.Many2one(
        'account.vat.period.end.statement', 'VAT statement'
    )
    amount = fields.Float(
        'Amount', required=True, digits=dp.get_precision('Account')
    )


class StatementGenericAccountLine(models.Model):
    _name = 'statement.generic.account.line'
    account_id = fields.Many2one(
        'account.account', 'Account', required=True
    )
    statement_id = fields.Many2one(
        'account.vat.period.end.statement', 'VAT statement'
    )
    amount = fields.Float(
        'Amount', required=True, digits=dp.get_precision('Account')
    )

    @api.onchange('account_id')
    def on_change_vat_account_id(self):
        self.amount = 0
        if self.account_id:
            self.amount = self.account_id.balance


class AccountTax(models.Model):
    _inherit = "account.tax"
    vat_statement_account_id = fields.Many2one(
        'account.account',
        "Account used for VAT statement",
        help="The tax balance will be "
             "associated to this account after selecting the period in "
             "VAT statement"
    )
    vat_statement_sign = fields.Integer(
        'Sign used in statement',
        help="If tax period sum is usually negative, set '-1' here",
        default=1
    )


class DateRange(models.Model):
    _inherit = "date.range"
    vat_statement_id = fields.Many2one(
        'account.vat.period.end.statement', "VAT statement"
    )
