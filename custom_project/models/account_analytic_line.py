from odoo import _, api, fields, models

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    _description = 'Account Analytic Line'
    
    project_id = fields.Many2one(comodel_name='project.project', string='Proyecto', readonly=True)