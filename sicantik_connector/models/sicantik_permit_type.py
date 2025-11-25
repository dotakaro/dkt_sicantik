# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError as UserError

_logger = logging.getLogger(__name__)


class SicantikPermitType(models.Model):
    """
    SICANTIK Permit Type Master Data

    Stores permit type information synced from SICANTIK.
    """

    _name = "sicantik.permit.type"
    _description = "SICANTIK Permit Type"
    _rec_name = "name"
    _order = "name"

    name = fields.Char(
        string="Permit Type Name",
        required=True,
        index=True,
        help="Name of the permit type (n_perizinan)",
    )

    code = fields.Char(string="Code", index=True, help="Permit type code")

    description = fields.Text(
        string="Description", help="Detailed description of this permit type"
    )

    active = fields.Boolean(
        string="Active", default=True, help="Whether this permit type is still active"
    )

    # Statistics
    permit_count = fields.Integer(
        string="Permit Count",
        compute="_compute_permit_count",
        store=False,
        help="Number of permits of this type",
    )

    active_permit_count = fields.Integer(
        string="Active Permits",
        compute="_compute_permit_count",
        store=False,
        help="Number of active permits of this type",
    )

    # Sync Information
    last_sync_date = fields.Datetime(
        string="Last Sync Date",
        readonly=True,
        help="Last time this record was synced from SICANTIK",
    )

    @api.model
    def _check_unique_name(self):
        for record in self:
            if (
                self.search_count([("name", "=", record.name), ("id", "!=", record.id)])
                > 0
            ):
                raise UserError("Permit type name must be unique!")

    @api.depends("name")
    def _compute_permit_count(self):
        """Compute permit counts"""
        for record in self:
            permits = self.env["sicantik.permit"].search(
                [("permit_type_name", "=", record.name)]
            )
            record.permit_count = len(permits)
            record.active_permit_count = len(
                permits.filtered(lambda p: p.status == "active")
            )

    def action_view_permits(self):
        """View permits of this type"""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": f"Permits - {self.name}",
            "res_model": "sicantik.permit",
            "view_mode": "list,form",
            "domain": [("permit_type_name", "=", self.name)],
            "context": {
                "default_permit_type_name": self.name,
                "default_permit_type_id": self.id,
            },
        }
