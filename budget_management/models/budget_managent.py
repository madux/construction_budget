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


class MasterBudget(models.Model):
    _name = "master.budget"
    _description = "Budget"
    _inherit = ['mail.thread']

    @api.model
    def create(self, vals):
        if vals.get('name', 'Budget Name') == 'Budget Name':
            vals['name'] = self.env['ir.sequence'].next_by_code('master.budget')# or '/'
        return super(MasterBudget, self).create(vals)

    name = fields.Char('Budget Name', required=True, states={'done': [('readonly', True)]},default='Budget Name')
    creating_user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    budget_master = fields.Many2one('master.budget', 'Master Budget') ######states={'done': [('readonly', True)]}
    project_name = fields.Many2one('project.project', 'Project Name')
    budget_category = fields.Selection([
        ('master', 'Master'),
        ('sub', 'Sub'),
        ], 'Budget Category', default='master', index=True, required=True, copy=False, track_visibility='always')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    budget_amount_after = fields.Float('Budget Amount After Variance', required=True,store=True, digits=0)
    budget_amount_before = fields.Float('Budget Amount Before Variance', required=True, digits=0,compute='get_general_budget_total')
    released_amount = fields.Float('Released Amount', required=True, digits=0)
    balance_amount = fields.Float(string='Balance Amount', default=0.0, compute='_compute_balance_amount' )
    approve_date = fields.Date('Approve Date', default = fields.Date.today())

    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    released_amount_date = fields.Date('Paid Date')
    purpose = fields.Text('Purpose', required=True)
    percentage = fields.Float(compute='_compute_percentage', string='Budget performance(%)',size=6)

    buildmain_budget_lines = fields.One2many('build.budget','master_build_line_id',string='Builidng')
    infrasture_budget_lines = fields.One2many('infrastructure.budget','master_build_line_id',string='Infrastructure')
    salaries_budget_lines = fields.One2many('salary.budget','master_build_line_id',string='Salaries')
    opex_budget_lines = fields.One2many('opex.budget','master_build_line_id',string='Opex')
    capex_budget_lines = fields.One2many('capex.budget','master_build_line_id',string='Capex')
    ancil_budget_lines = fields.One2many('ancil.budget','master_build_line_id',string='Anciliary')

    @api.depends('buildmain_budget_lines.budget_amount_before','infrasture_budget_lines.total_amount',
                'salaries_budget_lines.total_amount','opex_budget_lines.total_amount','capex_budget_lines.total_amount','ancil_budget_lines.budget_amount_before')
    def get_general_budget_total(self):
        total_build = 0.0
        total_infra = 0.0
        total_ancil = 0.0
        total_opexx = 0.0
        total_capex = 0.0
        total_salar = 0.0

        for rec in self:

            for ret in rec.buildmain_budget_lines:
                total_build += ret.budget_amount_before
            for ret2 in rec.infrasture_budget_lines:
                total_infra += ret2.total_amount
            for ret3 in rec.salaries_budget_lines:
                total_salar += ret3.total_amount
            for ret4 in rec.opex_budget_lines:
                total_opexx += ret4.total_amount
            for ret5 in rec.capex_budget_lines:
                total_capex += ret5.total_amount
            rec.budget_amount_before = total_build + total_infra + total_ancil + total_opexx + total_capex + total_salar
            #rec.budget_amount_before = sum((total_build,total_infra,total_ancil,total_opexx,total_capex,total_salar))

    @api.multi
    def _compute_percentage(self):
        #line.percentage = float((line.planned_amount or 0.0) / line.practical_amount) * 100
        for line in self:
            if line.budget_amount_before != 0.00:
                line.percentage = float((line.budget_amount_before or 0.0) / line.balance_amount) * 100
            else:
                line.percentage = 0.00

    @api.depends('budget_amount_after','budget_amount_before')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = rec.budget_amount_before - rec.budget_amount_after

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
            raise ValidationError('You cannot delete a confirm or validated budget')

        return super(MasterBudget, self).unlink()

class AnciliaryBudget(models.Model):
    _name = "ancil.budget"
    _description = "Ancilliary Budget"
    master_build_line_id = fields.Many2one('master.budget', 'Master Budget', )
    budget_amount_before = fields.Float('Budget Amount Before Variance', default=0.0, digits=0)



class BuildBudget(models.Model):
    _name = "build.budget"
    _description = "Building Budget"

    master_build_line_id = fields.Many2one('master.budget', 'Master Budget', )
    name = fields.Char('Budget Name', required=True, default='New')
    creating_user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    project_name = fields.Many2one('project.project', 'Project Name')
    budget_category = fields.Selection([
        ('master', 'Master'),
        ('sub', 'Sub'),
        ], 'Budget Category', default='sub', index=True, required=True, copy=False, track_visibility='always')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    budget_amount_before = fields.Float('Budget Amount Before Variance',compute='compute_overall_total', required=True, digits=0)
    budget_amount_after = fields.Float('Budget Amount After Variance', required=True, digits=0)
    released_amount = fields.Float('Released Amount', required=True, digits=0)

    date_from = fields.Date('Start Date', required=True, default = fields.Date.today())
    date_to = fields.Date('End Date', required=True, default = fields.Date.today())
    released_amount_date = fields.Date('Paid Date',required=True)
    approve_date = fields.Date('Approve Date', default = fields.Date.today())
    purpose = fields.Text('Purpose', required=True)
    total_plots = fields.Integer(compute='get_lenght_no', string='Total Plots',default=0)
    total_activities = fields.Integer(compute='get_lenght_no', string='Total Activities',default=0)
    total_blocks= fields.Integer(string='Total Blocks',default=0,compute='get_lenght_no')
    build_budget_lines = fields.One2many('build.budget.line','build_line_id',string='Builidng')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')

    '''@api.depends('product_id')
    def len_event(self):
        for rec in self:
            count = len(rec.product_id)
            rec.total_rooms = count

    @api.depends('room_lines.product_id')
    def get_lenght_no(self):

        for rec in self:

            count = len(rec.room_lines)
            rec.total_rooms = count
    #filex = fields.Binary("Upload File")'''

    @api.multi
    def confirm_budget(self):
        self.write({'state':'confirm'})
    @api.multi
    def cancel_budget(self):
        mas_budget_obj = self.env['master.budget']
        for line in self:
            mas_search = mas_budget_obj.search([('salaries_budget_lines','=',self.id)])
            if mas_search:
                mas_search.unlink()

            line.write({'state':'cancel'})

    @api.multi
    def validate_budget(self):
        for rec in self:
            id_main = []
            get_budget_id = self.env['master.budget'].search([('id','=',self.master_build_line_id.id)])
            if get_budget_id:
                id_main.append(rec.id)
                get_budget_id.buildmain_budget_lines = [(6,0,id_main)]
                rec.state = "validate"

    @api.depends('build_budget_lines.estimate_amount')
    def compute_overall_total(self):
        total = 0.0
        for rec in self:
            for ret in rec.build_budget_lines:
                total += ret.estimate_amount
            rec.budget_amount_before = total# + rec.budget_amount_before

    @api.depends('build_budget_lines')
    def get_lenght_no(self):
        pass
        '''for rec in self:
            if rec.build_budget_lines:
                leng_block = len(rec.build_budget_lines.block)
                leng_act = len(rec.build_budget_lines.activity_stage_id)
                leng_plot = len(rec.build_budget_lines.project_name)
                rec.total_blocks = leng_block
                rec.total_activities = leng_act
                rec.total_plots = leng_plot

    @api.depends('pow_lined.work')
    def len_event(self):
        for rec in self:
            count = len(rec.pow_lined)
            rec.number_work = count'''

    '''@api.model
    def create(self,values):
        budget_id = values.get('master_build_line_id')
        master_bud = self.env['master.budget'].search([('id','=',budget_id)])
        record = super(BuildBudget, self).create(values)

        master_bud.buildmain_budget_lines = budget_id#[(6,0,[budget_id])]

        return record'''

    @api.multi
    def set_draft_budget(self):
        self.state = "draft"
    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        if self.state in "confirm" or "validate":
            raise ValidationError('You cannot delete a confirmed or validated Budget')

        return super(BuildBudget, self).unlink()



class BuildLineBudget(models.Model):
    _name = "build.budget.line"
    _description = "Building Budget"
    build_line_id = fields.Many2one('build.budget', string='Budget')
    project_name = fields.Many2one('unit.masterx', 'Plot/Unit')   #('project.project', 'Project Name') ################ please insert plot.allocate inside project
    block = fields.Many2one('block.masterx', 'Block')
    house_type = fields.Many2one('building.masterx', 'House type')
    activity_stage_id = fields.Many2one('stage.activity.line', string = 'Activity/Stage')
    quantity = fields.Float('Quantity', digits=0)
    type_id = fields.Boolean('Type', default=True)

    amount_in_qty = fields.Float('Qty Amount', compute='get_act_stage_total', digits=0)
    estimate_amount = fields.Float('Estimate Budget', store=True, digits=0)  #
    create_date = fields.Date('Created Date', default = fields.Date.today())

    @api.depends('activity_stage_id')
    def get_act_stage_total(self):
        for ret in self:
            sta_act_total = ret.activity_stage_id.total_amount
            ret.amount_in_qty = sta_act_total

    @api.onchange('amount_in_qty','quantity')
    def get_amount_total(self):
        for rec in self:
            total = rec.amount_in_qty * rec.quantity
            rec.estimate_amount = total


class StageAndActivities(models.Model):
    _name = "stage.activity.line"
    _description = "Stage and Activities Budget"

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            res.append(
                (record.id,
                 record.boq.boq_name_x))
        return res

    boq = fields.Many2one('bill.quantity', string='BoQ')
    stage = fields.Many2one('activity.customx', string = 'Stage',required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    total_amount = fields.Float('Total Amount', compute='get_task_totals', digits=0)
    stage_activity_lines = fields.One2many('activity.task.line','task_act_id',string='Task / Activities',store=True)#, readonly=False,compute='get_tasks_and_append')

    """On change of boq, stage is been filtered by the stages in the stage_totals of that BoQ"""
    @api.onchange('boq')
    def domain_get_boq_task(self):
        domain = {}
        all_stage = []
        for ret in self:
            if self.boq:
                search_boq = self.env['bill.quantity'].search([('id','=',ret.boq.id)])
                for items in search_boq.stage_totals:
                    all_stage.append(items.stage_id.id)
                    domain = {'stage':[('id','=', all_stage)]}
        return domain

    """Calculates the totals of the amount in the stage activity line"""
    @api.depends('stage_activity_lines')
    def get_task_totals(self):
        total = 0.0
        for rec in self:
            if rec.stage_activity_lines:
                for ret in rec.stage_activity_lines:
                    total += ret.total_amount
                rec.total_amount = total

    """On selection of stage, it appends all stage_id from bill.of.quantity.stage ids to activity line - stage_id.id"""
    '''@api.depends('stage')
    def get_tasks_and_append(self):
        for rec in self:
            task_comm = []
            total = 0.0
            get_stage_and_act = self.env['bill.quantity'].search([('id','=',rec.boq.id)])
            for level in get_stage_and_act.stage:
                task_id = self.env['bill.of.quantity.stage'].search([('stage_id','=',level.stage_id.id)])

                task_comm.append((0,0,{'activity_task':level.stage_id.id}))#,'total_amount':level.total_dummy}))
            rec.stage_activity_lines = task_comm'''
    @api.onchange('stage')
    def get_tasks_and_append(self):
        for rec in self:
            task_comm = []
            total = 0.0
            get_stage_and_act = self.env['bill.quantity'].search([('id','=',rec.boq.id)])
            for level in get_stage_and_act.stage:
                task_id = self.env['bill.of.quantity.stage'].search([('stage_id','=',level.stage_id.id)])

                task_comm.append((0,0,{'activity_task':level.stage_id.id}))
                rec.stage_activity_lines = task_comm




"""On change or selection of activity_task, get the whole bill.of.quantity.stage where
    activity_task = same and write its whole material items to stage_datas_material, and
    labour items to stage_datas_labour

    Idea: On clicking of activity.task.line, the records of material and labour is displayed
    Total will be calculated from the totals of stage_datas_material and  stage_datas_labour """
class BuildingActivitiesTaskLines(models.Model):
    _name = "activity.task.line"
    _description = "Task and Activities Line"
    task_act_id = fields.Many2one('stage.activity.line', string='Task Id')
    infrastru_act_id =fields.Many2one('infrastructure.budget', string='Infrastructure Id')
    activity_task = fields.Many2one('project.task.type', string = 'Activity')
    total_amount = fields.Float('Total Amount', compute='get_all_task_totals', digits=0)
    #stage_datas_material = fields.One2many('bill.of.quantity.stage.data','stage_mat_id',string='Stage Material Line',store=True, compute='get_tasks_and_append')
    #stage_datas_labour = fields.One2many('bill.of.quantity.stage.data.labor','stage_lab_id',string='Stage Labour Line',store=True, compute='get_tasks_and_append')
    stage_datas_material = fields.Many2many('bill.of.quantity.stage.data',string='Stage Material Line',store=True, compute='get_tasks_and_append')
    stage_datas_labour = fields.Many2many('bill.of.quantity.stage.data.labor',string='Stage Labour Line',store=True, compute='get_tasks_and_append')

    """on change of activity_task, get all records of bill.of.quantity.stage where stage id = activity_task, append or write all
        the material and labour lines  """
    @api.depends('activity_task')
    def get_tasks_and_append(self):
        for rec in self:
            task_comm = []
            stage_materials = []
            labour_data = []
            total = 0.0
            get_stage_and_act = self.env['bill.of.quantity.stage'].search([('stage_id','=',rec.activity_task.id)])
            for lev in get_stage_and_act:
                for level in lev.stage_datas_material:
                    stage_materials.append(level.id)
                for level2 in lev.stage_datas_labour:
                    labour_data.append(level.id)
            rec.stage_datas_material = [(6,0,stage_materials)]
            rec.labour_data = [(6,0,labour_data)]

    """The total amount of all the activities totals in bill of quantity stage table"""

    @api.depends('stage_datas_material','stage_datas_labour')
    def get_all_task_totals(self):
        for rec in self:
            total_mat = 0.0
            total_lab = 0.0
            for ret in rec.stage_datas_material:
                total_mat += ret.total
            for rex in rec.stage_datas_labour:
                total_lab += rex.amount_total
            overall_total = total_lab + total_mat
            rec.total_amount =overall_total




'''class Bill_stage_Data(models.Model):
    _inherit = ['bill.of.quantity.stage.data']

    stage_mat_id = fields.Many2one('activity.task.line', string='Material Id')
class Bill_stage_Labour(models.Model):
    _inherit = ['bill.of.quantity.stage.data.labor']
    stage_lab_id = fields.Many2one('activity.task.line', string='Labour Id')'''

class ProductInherit(models.Model):
    _inherit = 'product.template'

    capex_period = fields.Selection([
        ('2018', '2018'),
        ('2019', '2019'),
        ('2020', '2020'),
        ('2021', '2021'),
        ('2022', '2022'),
        ('2023', '2023'),
        ('2024', '2023'),
        ('2025', '2025'),
        ], 'Period', default='2019', index=True, required=True, readonly=False, copy=False, track_visibility='always')



class InfrastructureModel(models.Model):
    _name = "infrastructure.budget"
    _description = "Infrastructure Budget"

    master_build_line_id = fields.Many2one('master.budget', 'Master Budget', )
    boq = fields.Many2one('bill.quantity', string='BoQ')
    stage = fields.Many2one('activity.customx', string = 'Stage',required=True)

    total_amount = fields.Float('Total Amount', compute='get_all_task_totals', digits=0)
    released_amount = fields.Float('Release Amount', digits=0)
    stage_activity_lines = fields.One2many('activity.task.line','infrastru_act_id',string='Task / Activities',store=True)#,compute='get_tasks_and_append')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')

    """creates and appends the activity id under stage_activity_lines with all activities found under stage"""
    @api.onchange('stage')
    def get_tasks_and_append(self):
        for rec in self:
            task_comm = []
            total = 0.0
            get_stage_and_act = self.env['bill.quantity'].search([('id','=',rec.boq.id)])
            for level in get_stage_and_act.stage:
                task_id = self.env['bill.of.quantity.stage'].search([('stage_id','=',level.stage_id.id)])

                task_comm.append((0,0,{'activity_task':level.stage_id.id}))
                rec.stage_activity_lines = task_comm
    """Gets the total of the calculations done in activity.task.line"""
    @api.depends('stage_activity_lines')
    def get_all_task_totals(self):
        for rec in self:
            total = 0.0
            for ret in rec.stage_activity_lines:
                total += ret.total_amount
            rec.total_amount = total

    @api.multi
    def set_draft_budget(self):
        self.state = "draft"
    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        #if self.state in "confirm" or "validate":

        if self.state in "confirm":# or "validate":
            raise ValidationError('You cannot delete a confirm budget')

        return super(InfrastructureModel, self).unlink()
    @api.multi
    def confirm_budget(self):
        self.write({'state':'confirm'})
    @api.multi
    def cancel_budget(self):
        self.write({'state':'cancel'})
        self.unlink()


    @api.multi
    def validate_budget(self):
        for rec in self:
            id_main = []
            get_budget_id = self.env['master.budget'].search([('id','=',self.master_build_line_id.id)])
            if get_budget_id:

                id_main.append((0,0, {'boq':rec.boq,'stage':rec.stage,'total_amount':rec.total_amount,}))
                get_budget_id.infrasture_budget_lines = id_main#(0,0, value)#{id_main})#[(0,0,id_main)]
                rec.state = "validate"



class OpexModel(models.Model):
    _name = "opex.budget"
    _description = "OPEX Budget"

    master_build_line_id = fields.Many2one('master.budget', 'Master Budget', )
    total_amount = fields.Float('Total Amount', compute='get_budget_total', digits=0)
    total_after = fields.Float('Total After Variance', compute='get_after_total', digits=0)
    released_amount = fields.Float('Release Amount', digits=0)
    approve_checkin_date = fields.Datetime('Approved Date', required=True, readonly=True, default=lambda *a: (datetime.datetime.now() + relativedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S'))#
    #checkout_date = fields.Datetime('Check Out', required=True, readonly=True,states={'draft': [('readonly', False)]},default=lambda *a: (datetime.datetime.now() + relativedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))#

    opex_lines = fields.One2many('opex.capex.line','opex_line_id',string='Opex Activities',store=True, readonly=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')

    @api.multi
    def confirm_budget(self):
        self.write({'state':'confirm'})
    @api.multi
    def cancel_budget(self):
        mas_budget_obj = self.env['master.budget']
        for line in self:
            mas_search = mas_budget_obj.search([('salaries_budget_lines','=',self.id)])
            if mas_search:
                mas_search.unlink()

            line.write({'state':'cancel'})

    @api.multi
    def validate_budget(self):
        for rec in self:
            id_main = []
            get_budget_id = self.env['master.budget'].search([('id','=',self.master_build_line_id.id)])
            if get_budget_id:
                id_main.append(rec.id)
                get_budget_id.opex_budget_lines = [(6,0,id_main)]
                rec.state = "validate"


    @api.depends('opex_lines.budget')
    def get_budget_total(self):
        for rec in self:
            total = 0.0
            for rex in rec.opex_lines:
                total += rex.budget
            rec.total_amount  = total
    @api.depends('released_amount','total_amount')
    def get_after_total(self):
        for rec in self:
            rec.total_after = rec.total_amount - rec.released_amount

    @api.multi
    def set_draft_budget(self):
        self.state = "draft"
    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        if self.state in "confirm" or "validate":
            raise ValidationError('You cannot delete a confirm or validated budget')

        return super(OpexModel, self).unlink()










class CapexModel(models.Model):
    _name = "capex.budget"
    _description = "CAPEX Budget"

    master_build_line_id = fields.Many2one('master.budget', 'Master Budget', )
    total_amount = fields.Float('Total Amount', compute='get_budget_total', digits=0)
    total_after = fields.Float('Total After Variance', compute='get_after_total', digits=0)
    released_amount = fields.Float('Release Amount', digits=0)
    approve_checkin_date = fields.Datetime('Approved Date', required=True, readonly=True, default=lambda *a: (datetime.datetime.now() + relativedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S'))#
    #checkout_date = fields.Datetime('Check Out', required=True, readonly=True,states={'draft': [('readonly', False)]},default=lambda *a: (datetime.datetime.now() + relativedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))#

    capex_lines = fields.One2many('opex.capex.line','capex_line_id',string='Opex Activities',store=True, readonly=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')

    @api.multi
    def confirm_budget(self):
        self.write({'state':'confirm'})
    @api.multi
    def cancel_budget(self):
        mas_budget_obj = self.env['master.budget']
        for line in self:
            mas_search = mas_budget_obj.search([('salaries_budget_lines','=',self.id)])
            if mas_search:
                mas_search.unlink()

            line.write({'state':'cancel'})

    @api.multi
    def validate_budget(self):
        for rec in self:
            id_main = []
            get_budget_id = self.env['master.budget'].search([('id','=',self.master_build_line_id.id)])
            if get_budget_id:
                id_main.append(rec.id)
                get_budget_id.capex_budget_lines = [(6,0,id_main)]
                rec.state = "validate"
    @api.depends('capex_lines.budget')
    def get_budget_total(self):
        for rec in self:
            total = 0.0
            for rex in rec.capex_lines:
                total += rex.budget
            rec.total_amount  = total
    @api.depends('released_amount','total_amount')
    def get_after_total(self):
        for rec in self:
            rec.total_after = rec.total_amount - rec.released_amount
    @api.multi
    def set_draft_budget(self):
        self.state = "draft"
    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        if self.state in "confirm" or "validate":
            raise ValidationError('You cannot delete a confirm or validated budget')

        return super(CapexModel, self).unlink()



class OpexCapexLine(models.Model):
    _name = "opex.capex.line"
    description = fields.Text('Payment For')
    month = fields.Selection([
        ('jan', 'January'),
        ('feb', 'Febuary'),
        ('mar', 'March'),
        ('apr', 'April'),
        ('may', 'May'),
        ('jun', 'June'),
        ('jul', 'July'),
        ('aug', 'August'),
        ('sep', 'September'),
        ('oct', 'October'),
        ('nov', 'November'),
        ('dec', 'December'),
        ], 'Month', default='jan', index=True, required=False, readonly=True, copy=False, track_visibility='always')


    period = fields.Selection([
        ('2018', '2018'),
        ('2019', '2019'),
        ('2020', '2020'),
        ('2021', '2021'),
        ('2022', '2022'),
        ('2023', '2023'),
        ('2024', '2023'),
        ('2025', '2025'),
        ], 'Month', default='2019', index=True, required=False, readonly=False, copy=False, track_visibility='always')

    product_id = fields.Many2one('product.template', string = 'Product')

    capex_line_id = fields.Many2one('capex.budget', string='Capex Id')
    opex_line_id = fields.Many2one('opex.budget', string='Opex Id')

    qty = fields.Float('Quantity',default=1.0)
    label = fields.Many2one('product.uom','Unit of Measure')
    rate = fields.Float('Rate',related='product_id.list_price')
    #total_before_variance = fields.Float('Total before Variance',compute='get_total')
    total = fields.Float('Total after Variance',compute='get_diff')
    budget = fields.Float('Budget Amount',compute='get_total')
    budget_release = fields.Float('Released Amount',default=0.0)

    #budget_after_var = fields.Float('Budget After Variance',compute='get_total')


    @api.depends('qty','rate')
    def get_total(self):
        for rec in self:
            totals = rec.qty * rec.rate
            rec.budget = totals
    @api.depends('budget','budget_release')
    def get_diff(self):
        for rec in self:
            rec.total = rec.budget - rec.budget_release

    """On change of period, it filters and appends all the products within the period"""
    @api.onchange('period')
    def filter_domain(self):
        domain = {}
        all_products = []
        for rec in self:
            get_products = self.env['product.template'].search([('capex_period','=', rec.period)])
            for items in get_products:
                all_products.append(items.id)
            domain = {'product_id':[('id','=',all_products)]}
        return domain



class SalaryBudgetModel(models.Model):
    _name = "salary.budget"
    _description = "Salary Budget"

    master_build_line_id = fields.Many2one('master.budget', 'Master Budget', )

    total_amount = fields.Float('Total Amount', compute='get_budget_total', digits=0)
    released_amount = fields.Float('Release Amount', digits=0)
    difference_budget = fields.Float('Difference Amount', compute='get_difference_total', digits=0)
    approve_checkin_date = fields.Datetime('Approved Date', required=True, readonly=True, default=lambda *a: (datetime.datetime.now() + relativedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S'))#
    salary_lines = fields.One2many('salary.budget.line','salary_line_id',string='Salary Lines',store=True, readonly=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done')
        ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, track_visibility='always')

    @api.multi
    def confirm_budget(self):
        self.write({'state':'confirm'})
    @api.multi
    def cancel_budget(self):
        mas_budget_obj = self.env['master.budget']
        for line in self:
            mas_search = mas_budget_obj.search([('salaries_budget_lines','=',self.id)])
            if mas_search:
                mas_search.unlink()

            line.write({'state':'cancel'})

    @api.multi
    def validate_budget(self):
        for rec in self:
            id_main = []
            get_budget_id = self.env['master.budget'].search([('id','=',self.master_build_line_id.id)])
            if get_budget_id:
                id_main.append(rec.id)
                get_budget_id.salaries_budget_lines = [(6,0,id_main)]
                rec.state = "validate"

    @api.depends('total_amount','released_amount')
    def get_difference_total(self):
        diff = 0.0
        for i in self:
            diff = i.total_amount - i.released_amount
        i.difference_budget = diff

    @api.depends('salary_lines')
    def get_budget_total(self):
        for rec in self:
            total = 0.0
            for rex in rec.salary_lines:
                total += rex.budget_total
            rec.total_amount = total

    @api.multi
    def set_draft_budget(self):
        self.state = "draft"

    @api.multi
    def unlink(self):
        """
        Overrides orm unlink method.
        @param self: The object pointer
        @return: True/False.
        """
        if self.state in "confirm" or "validate":
            raise ValidationError('You cannot delete a confirm or validated budget')

        return super(SalaryBudgetModel, self).unlink()



class SalaryBudgetLine(models.Model):
    _name = "salary.budget.line"

    months = fields.Selection([
        ('1', '1 Month'),
        ('2', '2 Months'),
        ('3', '3 Months'),
        ('4', '4 Months'),
        ('5', '5 Months'),
        ('6', '6 Months'),
        ('7', '7 Months'),
        ('8', '8 Months'),
        ('9', '9 Months'),
        ('10', '10 Months'),
        ('11', '11 Months'),
        ('12', '12 Months'),
        ], 'Months', default='1', index=True, required=False, readonly=False, copy=False, track_visibility='always')

    employee_id = fields.Many2one('hr.employee', string = 'Employee')
    dept_ids = fields.Char(string ='Department', related='employee_id.department_id.name',readonly = True, store =True)
    job_title = fields.Char(string = 'Job title',related ="employee_id.job_id.name")
    wage = fields.Float('Employee Wage',compute='get_employee_wage', default=0.0)
    budget_total= fields.Float('Budget Amount',compute='get_employee_wage',default=0.0)
    salary_line_id = fields.Many2one('salary.budget', string='Salary Id')
    duration = fields.Integer('Month Interval',compute='get_interval_wage')

    @api.depends('employee_id')
    def get_employee_wage(self):
        for rec in self:
            wage = 0.0
            get_wage = self.env['hr.contract'].search([('employee_id','=',rec.employee_id.id)])
            rec.wage = get_wage.wage
            rec.budget_total = wage * rec.duration


    @api.depends('months')
    def get_interval_wage(self):

        for rec in self:
            if rec.months == "1":
                rec.duration = 1
            elif rec.months == "2":
                rec.duration = 2

            elif rec.months == "3":
                rec.duration = 3

            elif rec.months == "4":
                rec.duration = 4
            elif rec.months == "5":
                rec.duration = 5
            elif rec.months == "6":
                rec.duration = 6
            elif rec.months == "7":
                rec.duration = 7
            elif rec.months == "8":
                rec.duration = 8
            elif rec.months == "9":
                rec.duration = 9
            elif rec.months == "10":
                rec.duration = 10
            elif rec.months == "11":
                rec.duration = 11
            elif rec.months == "12":
                rec.duration = 12
