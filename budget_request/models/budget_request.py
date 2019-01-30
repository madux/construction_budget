from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import except_orm, ValidationError

from dateutil.relativedelta import relativedelta
import datetime
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.tools.misc import formatLang

from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
import odoo.addons.decimal_precision as dp


class Budget_Request(models.Model): #budget.material.request budget.requestz budget.labour.request
    _name = "budget.requestz"
    _description = "Budget Reguest"


    @api.model
    def create(self, vals):
        if vals.get('name', 'Name') == 'Name':
            vals['name'] = self.env['ir.sequence'].next_by_code('finance.plan')# or '/'
        return super(Budget_Request, self).create(vals)



    name = fields.Char('Name', required=True,default='Name')
    creating_user_id = fields.Many2one('res.users', 'Prepared By', default=lambda self: self.env.user)
    budget_ref = fields.Many2one('build.budget', 'Master Budget', required=True)
    boq_id = fields.Many2one('bill.quantity', 'Bill of Quantity', required=True)

    budget_cost_total = fields.Float('Budget Cost', required=True,store=True, digits=0)
    actual_work_complete = fields.Float('(%) Actual Work Completed',store=True, digits=0)
    total_work_complete = fields.Float('(%) Work Completed',store=True, digits=0)

    actual_cost_total = fields.Float('Total Actual Cost', required=False,store=True, digits=0)
    amount_cost = fields.Float('Total Amount Cost', required=True,store=True, digits=0)
    var_outstanding = fields.Float('Variance, Difference)', required=False,store=True, digits=0)

    budget_mat_lines = fields.One2many('budget.material.request','master_req_mat_id', store=True,string='Material Request ')
    budget_lab_lines = fields.One2many('budget.labour.request','master_req_lab_id',store=True,string='Infrastructure')




    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirm'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')
    approve_date = fields.Date('Approve Date', default = fields.Date.today())

    @api.multi
    def confirm_budget(self):
        self.write({'state':'confirm'})
    @api.multi
    def cancel_budget(self):
        for line in self:
            line.write({'state':'cancel'})

    @api.multi
    def validate_budget(self):
        rec.state = "validate"
        rec.approve_date = fields.Date.today()

    @api.multi
    def set_draft_budget(self):
        rec.state = "draft"
    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        if self.state in "confirm" or "validate":
            raise ValidationError('You cannot delete a confirm or validated Plan')

        return super(Budget_Request, self).unlink()

class MaterialBudgetLine(models.Model):
    _name = "budget.material.request"
    _description = "Material Budget Reguest"

    name = fields.Char('Description', required=True,default='Name')
    master_req_mat_id = fields.Many2one('budget.requestz', 'Budget Request ID')

    product_id = fields.Many2one('product.product','Product', required=True)
    budget_cost = fields.Float('Budget Cost', required=True, digits=0)
    actual_cost = fields.Float('Actual Cost', compute="get_total_qty",required=True,store=True, digits=0)
    actual_quantity = fields.Float('Actual Quantity',store=True, digits=0)
    request_quantity = fields.Float('Requested Quantity',store=True, digits=0)
    used_quantity = fields.Float('Used Quantity',store=True, digits=0)
    difference = fields.Float('Difference', required=False,store=True, digits=0)
    approve_date = fields.Date('Approve Date', default = fields.Date.today())
    amount_cost = fields.Float('Amount Cost', required=True,store=True, digits=0)
    quantity_rem = fields.Float('Remaining Quantity', required=False,store=True, digits=0)

    #####
    project_name = fields.Many2many('project.project', string='Project Name')
    ## budget -->buildbudget (plot) =total) --> and total the( get{estimate amount})

    @api.onchange('project_name')
    def get_total_amount_plot(self):
        total = 0.0
        for rec in self:

            get_in = self.env['build.budget'].search([])
            for plot in rec.project_name:
                for x in get_in:
                    if x.project_name.id == plot.id:
                        total += x.budget_amount_before



                                #           rec.actual_quantity += reh.total_amount
            rec.budget_cost = total


    @api.depends('product_id')
    def get_total_qty(self):
        total = 0.0
        for rec in self:
            if rec.product_id:
                for r in rec.product_id:
                    rec.actual_cost = r.lst_price


    '''@api.depends('product_id')
    def get_total_qty(self):
        total = 0.0
        app=[]
        for rec in self:

            get_in = self.env['build.budget'].search([])
            for plot in rec.project_name:
                for x in get_in:
                    if x.project_name.id == plot.id:
                        for buildline in x.build_budget_lines:
                            for reh in buildline.activity_stage_id:
                                for rot in reh.stage_activity_lines:
                                    for tot in rot.stage_datas_material:

                                            if tot.product_id.id == rec.product_id.id: #
                                                app.append(tot.id)
                                                total += tot.qty
                                                rec.actual_quantity = total
            rec.actual_cost = rec.product_id.lst_price'''


                                #           rec.actual_quantity += reh.total_amount

    @api.onchange('actual_cost')
    def get_difference(self):
        difference= self.actual_cost - self.budget_cost
        self.difference = difference


    @api.onchange('actual_cost')
    def get_remaining_qty(self):
        rem_quantity = self.used_quantity - self.request_quantity
        self.quantity_rem= rem_quantity






class LabourBudgetLine(models.Model):
    _name = "budget.labour.request"
    _description = "Labour Budget Reguest"

    master_req_lab_id = fields.Many2one('budget.requestz', 'Budget Request ID')
    name = fields.Char('Description', required=True,default='Name')
    activity = fields.Many2one('project.task.type', 'Labour Activity',compute="get_change_records")
    budget_cost = fields.Float('Budget Cost', required=True,store=True, digits=0)
    work_complete = fields.Float('(%) Work Completed',store=True, digits=0)
    actual_cost = fields.Float('Actual Cost', required=True,store=True, digits=0)
    amount_cost = fields.Float('Amount Cost', required=True,store=True, digits=0)
    outstanding = fields.Float('Outstanding', required=False,store=True, digits=0)
    balance = fields.Float('Balance', required=False,store=True, digits=0)
    difference = fields.Float('Difference', required=False,store=True, digits=0)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Paid'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')
    approve_date = fields.Date('Approve Date', default = fields.Date.today())

    @api.depends('activity')
    def get_change_records(self):
        get_in = self.env['build.budget'].search([])
        appends= []
        total = 0.0
        for ref in get_in:
            for rec in ref.build_budget_lines:
                for rex in rec.activity_stage_id:
                    for rel in rex.stage_activity_lines:
                        for rem in rel.stage_datas_labour:
                            if rem.activity_task.id == ret.activity.id:
                                total += rem.amount_total
            ret.budget_cost = total


