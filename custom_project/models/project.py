from odoo import _, api, fields, models
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

# It is specified that the account will be of type Expenses ID
ACCOUNT_ACCOUNT_TYPE_ID = 15


class ProjectProject(models.Model):
    _inherit = 'project.project'
    _description = 'Project Project'

    monto_acumulado = fields.Monetary(string="Monto acumulado", currency_field="currency_id")
    show_btn_to_close = fields.Boolean(compute='compute_close_project')
    show_btn_to_ubication = fields.Boolean(compute='compute_to_ubication')
    show_btn_to_analytic_account = fields.Boolean(compute='compute_to_analytic_account')
    show_btn_reopen = fields.Boolean(compute='compute_reopen_project')
    show_account = fields.Boolean(compute='compute_show_account')
    state_project = fields.Selection(selection=[("open", "Abierto"), ("close", "Cerrado")], default="open")
    account_account = fields.Many2one(comodel_name='account.account', string='Cuenta Contable',
                                      domain="[('user_type_id', '=', " + str(ACCOUNT_ACCOUNT_TYPE_ID) + ")]")
    product_tmpl_id = fields.Many2one(comodel_name='product.template', string='Activo fijo', readonly=True)
    tag_ids = fields.Many2many('project.tags', relation='project_project_project_tags_rel', string='Tags')
    stock_location_id = fields.Many2one('stock.location', string='Ubicacion en inventario', compute='_compute_stock_location', store=True, readonly=False)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta Analítica', compute='_compute_analytic_account', store=True, readonly=False)
    info_message_analytic = fields.Html(string='Información de Cuenta Analítica', compute='_compute_info_message', readonly=True, sanitize=False)


    def write(self, vals):
        for project_id in self:
            if project_id.state_project == 'close' and not \
                    ('state_project' in vals and self.user_has_groups('project.group_project_manager')) and\
                    not ('product_tmpl_id' in vals):
                raise UserError(_("No se puede modificar un proyecto cerrado."))
        if vals.get('analytic_account_id') != self.analytic_account_id.id and self.analytic_account_id.line_ids.filtered(lambda x: x.project_id.id == self.id):
            raise UserError(_("No se puede modificar la cuenta analítica de un proyecto que ya tiene lineas analiticas.\n Elimine la linea analítica del proyecto primero."))
        res = super(ProjectProject, self).write(vals)
        self._create_account_analytic_line(vals)
        return res

    @api.model
    def create(self, vals):
        res = super(ProjectProject, self).create(vals)
        res._create_account_analytic_line(vals)
        return res

    def _create_account_analytic_line(self, vals):
        analytic_account = vals.get('analytic_account_id', self.analytic_account_id.id)
        monto_acumulado = vals.get('monto_acumulado', self.monto_acumulado)
        analytic_account_id = self.env['account.analytic.account'].browse(analytic_account) if analytic_account else False
        line_ids = analytic_account_id.line_ids if analytic_account_id else []
        if monto_acumulado and analytic_account:
            if  len(line_ids) == 0:
                self.env['account.analytic.line'].create({
                    'name': self.name,
                    'account_id': analytic_account_id.id,
                    'date': fields.Date.today(),
                    'amount': monto_acumulado,
                    'company_id': self.company_id.id,
                    'project_id': self.id,
                })
            elif len(line_ids) == 1 and line_ids[0].name == self.name and line_ids[0].account_id.id == analytic_account_id.id:
                line_ids[0].amount = monto_acumulado

    def cron_create_account_analytic_line(self):
        records = self.browse([])
        for record in records:
            try:
                record._create_account_analytic_line({})
            except Exception as error:
                _logger.error(f'Error al crear línea de cuenta analítica: {error}\n del projecto {record.name}')
            else:
                continue

    def compute_reopen_project(self):
        for project_id in self:
            project_id.show_btn_reopen = True if (
                    project_id.state_project == 'close' and self.user_has_groups('project.group_project_manager')
            ) else False

    def compute_show_account(self):
        for project_id in self:
            if project_id.date:
                project_id.show_account = True if project_id.date <= fields.Date.today() else False
            else:
                project_id.show_account = False

    def compute_close_project(self):
        for project_id in self:
            if project_id.date:
                project_id.show_btn_to_close = True if (
                        project_id.date <= fields.Date.today() and project_id.state_project == 'open'
                ) else False
            else:
                project_id.show_btn_to_close = False

    def reopen_project(self):
        for project_id in self:
            project_id.sudo().state_project = 'open'

    def close_project(self):
        for project_id in self:
            if not project_id.account_account:
                raise UserError(_("No se puede cerrar el proyecto sin una cuenta de gastos definida."))
            project_id.state_project = 'close'

    def button_fixed_asset(self):
        if self.product_tmpl_id:
            raise UserError(_("No se puede volver a crear el activo fijo una vez creado."))
        product_category_id = self.env['product.category'].search([('is_asset', '=', True)], limit=1)
        product_tmpl_id = self.env['product.template'].create({
            "name": self.name,
            "standard_price": self.monto_acumulado,
            "is_asset": True,
            "categ_id": product_category_id.id,
        })
        self.product_tmpl_id = product_tmpl_id

    @api.depends('name', 'partner_id', 'tag_ids', 'user_id', 'date_start')
    def compute_to_ubication(self):
        for project_id in self:
            if project_id.stock_location_id:
                project_id.show_btn_to_ubication = False
            elif (
                project_id.name
                and project_id.partner_id
                and project_id.tag_ids
                and project_id.user_id
                and project_id.date_start
            ):
                project_id.show_btn_to_ubication = True
            else:
                project_id.show_btn_to_ubication = False

    @api.depends('analytic_account_id', 'name', 'partner_id')
    def compute_to_analytic_account(self):
        for project_id in self:
            if project_id.analytic_account_id:
                project_id.show_btn_to_analytic_account = False
            elif project_id.name and project_id.partner_id:
                project_id.show_btn_to_analytic_account = True
            else:
                project_id.show_btn_to_analytic_account = False

    def get_stock_location(self, location_id, location_id_2):
        stock_location = self.env['stock.location'].search([
            ('location_id', '=', location_id),
            ('id', '=', location_id_2)
        ], limit=1)

        return stock_location

    @api.depends('name')
    def _compute_stock_location(self):
        for project in self:
            specific_location = self.get_stock_location(7, 8)
            if specific_location:
                location_id = specific_location.id
            else:
                location_id = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1).id
            existing_location = self.env['stock.location'].search([
                ('name', '=', project.name),
                ('location_id', '=', location_id),
                ('usage', '=', 'production')
            ], limit=1)
            project.stock_location_id = existing_location if existing_location else False

    def send_to_ubication(self):
        for project in self.sudo():
            if project.stock_location_id:
                raise UserError('El proyecto ya existe en una determinada ubicación y se ha ligado automáticamente a la ubicación que está relacionada una vez que se ejecutó "enviar a ubicación".')
            else:
                specific_location = self.get_stock_location(7, 8)
                if specific_location:
                    location_id = specific_location.id
                else:
                    location_id = self.env['stock.location'].sudo().search([('usage', '=', 'internal')], limit=1).id
                existing_location = self.env['stock.location'].sudo().search([
                    ('name', '=', project.name),
                    ('location_id', '=', location_id),
                    ('usage', '=', 'production')
                ], limit=1)
                if existing_location:
                    project.stock_location_id = existing_location
                    raise UserError('El proyecto ya existe en una determinada ubicación y se ha ligado automáticamente a la ubicación que está relacionada una vez que se ejecutó "enviar a ubicación".')
                else:
                    vals = {
                        'name': project.name,
                        'location_id': location_id,
                        'usage': 'production',
                        'employee_id': None,
                    }
                    new_location = self.env['stock.location'].sudo().create(vals)
                    project.stock_location_id = new_location

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.location',
                'view_mode': 'form',
                'res_id': project.stock_location_id.id,
                'target': 'current',
            }

    @api.depends('name', 'partner_id')
    def _compute_analytic_account(self):
        for project in self:
            if project.name and project.partner_id:
                existing_analytic_account = self.env['account.analytic.account'].search([
                    ('name', '=', project.name),
                    ('partner_id', '=', project.partner_id.id),
                ], limit=1)

                if existing_analytic_account:
                    project.analytic_account_id = existing_analytic_account.id
                else:
                    project.analytic_account_id = False
            else:
                project.analytic_account_id = False

    @api.depends('name', 'partner_id')
    def _compute_analytic_account(self):
        for project in self:
            if project.name and project.partner_id:
                existing_analytic_account = self.env['account.analytic.account'].search([
                    ('name', '=', project.name),
                    ('partner_id', '=', project.partner_id.id),
                ], limit=1)
                
                if existing_analytic_account:
                    project.analytic_account_id = existing_analytic_account.id
                else:
                    project.analytic_account_id = False
            else:
                project.analytic_account_id = False

    def send_to_analytic_account(self):
        for project in self:
            if project.analytic_account_id:
                raise UserError(_('El proyecto ya tiene una cuenta analítica asociada.'))
            else:
                if project.name and project.partner_id:
                    existing_analytic_account = self.env['account.analytic.account'].search([
                        ('name', '=', project.name),
                        ('partner_id', '=', project.partner_id.id),
                    ], limit=1)

                    if existing_analytic_account:
                        project.analytic_account_id = existing_analytic_account.id
                    else:
                        vals = {
                            'name': project.name,
                            'partner_id': project.partner_id.id,
                        }
                        new_analytic_account = self.env['account.analytic.account'].create(vals)
                        project.analytic_account_id = new_analytic_account.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.account',
            'view_mode': 'form',
            'res_id': project.analytic_account_id.id,
            'target': 'current',
        }

    def _compute_info_message(self):
        for project in self:
            if project.analytic_account_id:
                project.info_message_analytic = ("¡¡Atencion!!. Si se necesita configurar cuenta analítica haga click arriba en el nombre de la cuenta analitica.")
            else:
                project.info_message_analytic = ("¡¡Atencion!!. No hay cuenta analítica relacionada. dar click el botón de 'Crear cuenta analitica' para crear una o relacionarla.")
