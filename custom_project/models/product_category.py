from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    is_asset = fields.Boolean(string='Es activo fijo?', default=False)
