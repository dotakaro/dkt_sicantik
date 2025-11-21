# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SicantikWhatsAppCleanupWizard(models.TransientModel):
    """
    Wizard untuk cleanup template WhatsApp yang sudah ada
    """

    _name = "sicantik.whatsapp.cleanup.wizard"
    _description = "Cleanup WhatsApp Templates Wizard"

    confirm_cleanup = fields.Boolean(
        string="Saya memahami konsekuensi dari tindakan ini",
        help="Centang kotak ini untuk mengkonfirmasi bahwa Anda memahami bahwa template akan dihapus permanen",
    )

    def action_cleanup_templates(self):
        """
        Hapus template WhatsApp SICANTIK yang sudah ada
        """
        self.ensure_one()

        if not self.confirm_cleanup:
            raise UserError(
                _(
                    "Anda harus mengkonfirmasi bahwa Anda memahami konsekuensi dari tindakan ini."
                )
            )

        template_names = [
            "izin_selesai_diproses",
            "dokumen_baru_untuk_tandatangan",
            "dokumen_perlu_approval",
            "update_status_perizinan",
            "reminder_dokumen_pending",
            "peringatan_masa_berlaku_izin",
            "perpanjangan_izin_disetujui",
        ]

        _logger.info("=" * 80)
        _logger.info("🧹 CLEANUP: Menghapus template WhatsApp SICANTIK yang sudah ada")
        _logger.info("=" * 80)

        # Cari template yang sudah ada
        existing_templates = self.env["whatsapp.template"].search(
            [("template_name", "in", template_names)]
        )

        if not existing_templates:
            _logger.info("✅ Tidak ada template yang perlu dihapus")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Cleanup Template",
                    "message": "Tidak ada template yang perlu dihapus",
                    "type": "info",
                },
            }

        _logger.info(
            f"📋 Ditemukan {len(existing_templates)} template yang akan dihapus"
        )

        # Hapus variabel terlebih dahulu
        for template in existing_templates:
            _logger.info(f"  Menghapus variabel untuk: {template.name}")
            template.variable_ids.unlink()

        # Hapus template
        template_names_list = [t.name for t in existing_templates]
        existing_templates.unlink()

        _logger.info(f"✅ Berhasil menghapus {len(template_names_list)} template")
        for name in template_names_list:
            _logger.info(f"  - {name}")

        _logger.info("=" * 80)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "✅ Cleanup Berhasil",
                "message": f"Berhasil menghapus {len(template_names_list)} template WhatsApp SICANTIK. Silakan upgrade modul sekarang.",
                "type": "success",
                "sticky": True,
            },
        }
