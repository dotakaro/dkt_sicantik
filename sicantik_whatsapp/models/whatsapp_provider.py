# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SicantikWhatsappProvider(models.Model):
    """
    Profil provider WhatsApp yang dapat dipilih oleh konfigurasi SICANTIK.
    Mendukung 3 tipe provider: Meta (official), Watzap.id, dan Fonnte.
    """

    _name = 'sicantik.whatsapp.provider'
    _description = 'SICANTIK WhatsApp Provider'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    provider_type = fields.Selection(
        selection=[
            ('meta', 'Meta (Official WhatsApp Business API)'),
            ('watzap', 'Watzap.id'),
            ('fonnte', 'Fonnte.com'),
        ],
        required=True,
        string='Provider Type',
        help='Jenis provider yang digunakan untuk mengirim pesan WhatsApp.',
    )
    description = fields.Text()
    is_default = fields.Boolean(
        string='Default Provider',
        help='Jika diaktifkan, provider ini akan digunakan sebagai default '
             'ketika konfigurasi lain belum memilih provider secara spesifik.',
    )

    # --- Meta / Official WhatsApp Settings ---
    meta_account_id = fields.Many2one(
        'whatsapp.account',
        string='Meta WhatsApp Account',
        help='Akun WhatsApp official Odoo Enterprise yang akan digunakan untuk '
             'mengirim pesan template resmi dari Meta.',
    )
    meta_namespace = fields.Char(
        string='Template Namespace',
        help='Opsional. Namespace template Meta jika diperlukan untuk integrasi lanjutan.',
    )

    # --- Watzap.id Settings ---
    watzap_base_url = fields.Char(
        string='Watzap API URL',
        default='https://api.watzap.id/v1',
        help='Endpoint dasar API Watzap.id.',
    )
    watzap_api_key = fields.Char(
        string='Watzap API Key',
        help='Token/credential yang diberikan oleh Watzap.id.',
    )
    watzap_device_id = fields.Char(
        string='Watzap Device/Sender ID',
        help='Identifier device/sender (misal nomor pengirim) di Watzap.',
    )
    watzap_callback_token = fields.Char(
        string='Watzap Callback Token',
        help='Token verifikasi untuk webhook Watzap, jika diperlukan.',
    )

    # --- Fonnte Settings ---
    fonnte_api_url = fields.Char(
        string='Fonnte API URL',
        default='https://api.fonnte.com',
        help='Endpoint dasar API Fonnte.',
    )
    fonnte_token = fields.Char(
        string='Fonnte Token',
        help='API token utama untuk Fonnte.',
    )
    fonnte_device = fields.Char(
        string='Fonnte Device ID',
        help='Device ID atau sender ID yang disediakan oleh Fonnte.',
    )
    fonnte_secret = fields.Char(
        string='Fonnte Secret/Callback Key',
        help='Key tambahan untuk verifikasi webhook atau enkripsi payload.',
    )

    # --- Utility Fields ---
    credential_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('configured', 'Configured'),
            ('error', 'Error'),
        ],
        string='Credential Status',
        default='draft',
        help='Status konfigurasi credential provider.',
    )

    last_error_message = fields.Text(readonly=True)

    @api.constrains('is_default', 'provider_type')
    def _check_single_default_per_type(self):
        """Pastikan hanya ada satu provider default per jenis provider."""
        for record in self:
            if record.is_default and record.provider_type:
                domain = [
                    ('id', '!=', record.id),
                    ('provider_type', '=', record.provider_type),
                    ('is_default', '=', True),
                ]
                if self.search_count(domain):
                    raise ValidationError(_(
                        'Hanya boleh ada satu provider default untuk tipe %s.'
                    ) % record.provider_type.upper())

    def mark_configured(self):
        """Helper untuk menandai credential sudah lengkap."""
        for record in self:
            record.credential_state = 'configured'
            record.last_error_message = False

    def mark_error(self, message):
        """Helper untuk menandai credential error."""
        for record in self:
            record.credential_state = 'error'
            record.last_error_message = message

    def get_provider_payload(self):
        """
        Kembalikan dictionary credential yang siap dipakai dispatcher.
        """
        self.ensure_one()
        return {
            'provider_type': self.provider_type,
            'meta_account_id': self.meta_account_id.id if self.meta_account_id else False,
            'meta_namespace': self.meta_namespace,
            'watzap': {
                'base_url': self.watzap_base_url,
                'api_key': self.watzap_api_key,
                'device_id': self.watzap_device_id,
                'callback_token': self.watzap_callback_token,
            },
            'fonnte': {
                'api_url': self.fonnte_api_url,
                'token': self.fonnte_token,
                'device': self.fonnte_device,
                'secret': self.fonnte_secret,
            },
        }

