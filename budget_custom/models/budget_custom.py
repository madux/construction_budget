from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import except_orm, ValidationError

from datetime import datetime, timedelta
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.tools.misc import formatLang

from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
import odoo.addons.decimal_precision as dp


class CustomBudget(models.Model):
    _name = "budget.custom"
    _description = "Budget"
    _inherit = ['mail.thread']

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('budget.custom')# or '/'
        return super(CustomBudget, self).create(vals)

    name = fields.Char('Budget Name', required=True, states={'done': [('readonly', True)]},default='New')
    creating_user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    date_from = fields.Date('Start Date', required=True, states={'done': [('readonly', True)]},compute="change_dates")
    date_to = fields.Date('End Date', required=True, states={'done': [('readonly', True)]},compute="change_dates")
    project_id = fields.Many2one('project.project', 'Project')
    purpose = fields.Text('Purpose', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')
    custom_budget_line = fields.One2many('custom.budget.lines', 'custom_budget_id', 'Budget Lines',
        states={'done': [('readonly', True)]}, copy=True)
    budget_material = fields.One2many('material.budget','material_line_id',string='Material Budget Line')

    company_id = fields.Many2one('res.company', 'Company', required=True,
        default=lambda self: self.env.user.company_id)

    @api.depends('custom_budget_line')
    def change_dates(self):

        for rec in self:
            if rec.custom_budget_line:
                period_start = rec.custom_budget_line[0].date_from
                period_end = rec.custom_budget_line[-1].date_to
                rec.date_from = period_start
                rec.date_to = period_end or rec.custom_budget_line[0].date_to
    @api.multi
    def confirm_button(self):
        self.write({'state':'confirm'})

    @api.multi
    def validate_button(self):
        self.write({'state':'validate'})

    @api.multi
    def done_button(self):
        self.write({'state':'done'})

    @api.multi
    def cancel_button(self):
        self.write({'state':'cancel'})

    @api.multi
    def set_draft_button(self):
        self.write({'state':'cancel'})



class CustomBudgetLines(models.Model):
    _name = "custom.budget.lines"
    _description = "Budget Line"


    custom_budget_id = fields.Many2one('budget.custom', 'Budget', ondelete='cascade', index=True, required=True)
    budget_categ = fields.Many2one('budget.categ','Budget', ondelete='cascade', index=True, required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')

    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    paid_date = fields.Date('Paid Date')
    planned_amount = fields.Float('Estimated Budget Amount', required=True, digits=0)
    practical_amount = fields.Float(string='Used Amount', default=1.0)#(compute='_compute_practical_amount', string='Actual Amount', digits=0)
    percentage = fields.Float(compute='_compute_percentage', string='Budget performance(%)',size=6)



    @api.multi
    def _compute_practical_amount(self):
        for line in self:
            result = 0.0

            date_to = self.env.context.get('wizard_date_to') or line.date_to
            date_from = self.env.context.get('wizard_date_from') or line.date_from
            if line.analytic_account_id.id:
                self.env.cr.execute("""
                    SELECT SUM(amount)
                    FROM account_analytic_line
                    WHERE account_id=%s
                        AND (date between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd'))
                        """,
                (line.analytic_account_id.id, date_from, date_to,))
                result = self.env.cr.fetchone()[0] or 0.0
            line.practical_amount = result


    @api.multi
    def _compute_percentage(self):
        #line.percentage = float((line.planned_amount or 0.0) / line.practical_amount) * 100
        for line in self:
            if line.planned_amount != 0.00:
                line.percentage = float((line.planned_amount or 0.0) / line.practical_amount) * 100
            else:
                line.percentage = 0.00

class Material_Budget(models.Model):
    _name = 'material.budget'

    material_line_id = fields.Many2one('budget.custom')
    product_id = fields.Many2one('product.product', string = 'Product')
    total_qty = fields.Float('Total Quantity')
    used_qty = fields.Float('Used Quantity',default=0.0)
    remain_qty = fields.Float('Remaining Quantity',compute='_remaining_qty')
    label = fields.Many2one('product.uom','Label')
    rate = fields.Float('Rate',related='product_id.list_price')

    total_before = fields.Float('Total Before Variance',compute='get_total')

    total_after = fields.Float('Total After Variance',compute='overall_total')


    @api.depends('rate','remain_qty')
    def overall_total(self):
        totals = 0.0
        for rec in self:
            totals = rec.remain_qty * rec.rate
            rec.total_after = totals



    @api.depends('total_qty','used_qty')
    def _remaining_qty(self):
        for rec in self:
            totals =rec.total_qty - rec.used_qty
            rec.remain_qty = totals


    @api.depends('total_qty','rate')
    def get_total(self):
        for rec in self:
            totals = rec.total_qty * rec.rate
            rec.total_before = totals

### On selection of analytic account, an click approve, it takes total dummy and minus the analytic account practical amount on budget custom.
###
class Budget_Building(models.Model):
    _name = 'building.budget'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('building.budget')# or '/'
        return super(Budget_Building, self).create(vals)

    name = fields.Char('Sequence', default='New')
    project_id = fields.Many2one('project.project', 'Project')
    plot_id = fields.Many2one('plot.allocatex', 'Plot')
    activity_id = fields.Many2one('project.task.type', string = 'Activity')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', required=True)
    budget_id = fields.Many2one('budget.custom', 'Budget Plan', required=True)

    date_from = fields.Date('Start Date')
    date_to = fields.Date('End Date')

    material_total = fields.Float('Material Total', compute='material_cost')
    labour_total = fields.Float('Labour Total',compute='labour_cost')

    activity_cus = fields.Many2one('activity.customx', string = 'Stage',required=True)

    stage_datas_material = fields.One2many('materialsub.budget','material_id',string='Stage Material Line')
    stage_datas_labour = fields.One2many('labor.budget','labor_line_id',string='Stage Labour Line')

    total_dummy = fields.Float('Total overall', store=True, compute='total_overall')
    state = fields.Selection([('draft','Draft'),('sub','Submitted'),('done','Done'),('cancel','Cancel')],string='State', default="draft")

    @api.onchange('budget_id')
    def budget_change(self):

        for ret in self:
            d_from = ret.budget_id.date_from
            d_to = ret.budget_id.date_to
            self.update({'date_from':d_from,'date_to':d_to})

    @api.multi
    def submit_items(self):
        self.write({'state':'sub'})

    @api.multi
    def cancel_button(self):
        self.write({'state':'cancel'})

    @api.multi
    def setdraft_button(self):
        self.write({'state':'draft'})

    @api.multi
    def approve_items(self):
        cbl_obj = self.env['custom.budget.lines']
        search_lines = cbl_obj.search([('analytic_account_id','=',self.analytic_account_id.id)])

        mat_budget = self.env['material.budget']

        # Checks if the selected budget item corresponds to the items material selected
        if not search_lines:
            raise ValidationError('The proposed analytic account is not in the budget')
        for rec in search_lines:

            if self.total_dummy > rec.planned_amount:
                raise ValidationError('You have gone out of the proposed budget for this account')
            else:
                planed_amount = rec.planned_amount
                rec.practical_amount = planed_amount - self.total_dummy
                self.write({'state':'done'})





        total_q = 0.0
        for rex in self.stage_datas_material:
            total_q =  rex.total_qty
            product = rex.product_id.id
        for reo in self.env['material.budget'].search([('product_id','=',product)]):

            if total_q > reo.remain_qty:
                raise ValidationError('You have gone out of the proposed budget for this item')
            else:
                reo.used_qty = reo.used_qty + rex.total_qty


    @api.depends('material_total','labour_total')
    def total_mat_lab(self):
        for rec in self:
            rec.total_dummy = rec.material_total + rec.labour_total


    @api.depends('stage_datas_material','stage_datas_labour')
    def total_overall(self):
        total_material = 0.0
        total_labour = 0.0
        for rec in self.stage_datas_material:
            total_material += rec.total

        for rem in self.stage_datas_labour:
            total_labour += rem.amount_total
        for ret in self:
            ret.total_dummy = total_material + total_labour
    #@api.one
    @api.depends('stage_datas_material')
    def material_cost(self):
        total_all = 0.0

        for rex in self:
            for rec in rex.stage_datas_material:
                total_all += rec.total
            rex.material_total =total_all

    #@api.one
    @api.depends('stage_datas_labour')
    def labour_cost(self):
        total_all = 0.0
        for rex in self:
            for rec in rex.stage_datas_labour:
                total_all += rec.amount_total
                rex.labour_total =total_all

########## Onchange of the product_id, it checks the remaining quantity in the budget and deduct the items.
class Material_Budget_sub(models.Model):
    _name = 'materialsub.budget'

    material_id = fields.Many2one('building.budget')
    product_id = fields.Many2one('product.product', string = 'Product')
    total_qty = fields.Float('Total Quantity',default=1.0)
    label = fields.Many2one('product.uom','Label')
    rate = fields.Float('Rate',related='product_id.list_price')
    total = fields.Float('Total',compute='get_total')

    @api.depends('total_qty','rate')
    def get_total(self):
        for rec in self:
            totals = rec.total_qty * rec.rate
            rec.total = totals

######### checks the total cost of everything and deducts or raises alert if the money is over the est.budget


class Labour_Budget(models.Model):
    _name = 'labor.budget'
    name = fields.Char('Labour Description')
    labor_line_id = fields.Many2one('building.budget')
    activity_id = fields.Many2one('project.task.type', string = 'Activity')
    qty = fields.Float('Quantity',default=1.0)

    rate = fields.Float('Rate',default=1.00)

    amount_total = fields.Float('Amount',compute='get_total')

    @api.depends('qty','rate')
    def get_total(self):
        for rec in self:
            totals = rec.qty * rec.rate
            rec.amount_total = totals





class Budget_Categ(models.Model):
    _name = 'budget.categ'
    name = fields.Char('Category')



