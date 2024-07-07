from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression


class Task(models.Model):
    _inherit = "project.task"

    payment_state = fields.Selection(
        [
            ("not_payment", "Pendiente de pago"),
            ("partial_payment", "Parcialmente pagado"),
            ("payment", "Pagado"),
        ],
        string="Estado de pago",
        default="not_payment",
    )
