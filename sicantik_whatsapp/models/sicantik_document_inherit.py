# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class SicantikDocument(models.Model):
    """
    Inherit model sicantik.document untuk menambahkan trigger notifikasi WhatsApp
    """
    _inherit = 'sicantik.document'
    
    def write(self, vals):
        """Override untuk trigger notifikasi WhatsApp saat status dokumen berubah"""
        result = super().write(vals)
        
        # Cek jika dokumen baru diupload dan status menjadi 'pending_signature'
        if vals.get('state') == 'pending_signature':
            self._kirim_notifikasi_dokumen_baru()
        
        # Cek jika dokumen perlu approval
        if vals.get('state') == 'pending_signature' and vals.get('requires_approval'):
            self._kirim_notifikasi_perlu_approval()
        
        return result
    
    def _kirim_notifikasi_dokumen_baru(self):
        """
        Kirim notifikasi WhatsApp ke staff saat dokumen baru masuk untuk ditandatangani
        Template: document_pending
        """
        for record in self:
            # Cari staff yang bertanggung jawab (bisa dari workflow atau default)
            # Untuk sementara, kita kirim ke semua user internal dengan nomor WhatsApp
            # Field mobile ada di res.partner, bukan res.users, jadi kita filter manual
            all_staff = self.env['res.users'].search([
                ('share', '=', False),
                ('active', '=', True)
            ])
            
            # Filter manual untuk user yang punya phone di partner_id
            # Di Odoo 18.4, hanya ada field 'phone', tidak ada 'mobile'
            def _has_phone(user):
                if not user.partner_id:
                    return False
                # Gunakan method _get_mobile_or_phone() jika ada, atau langsung akses phone
                if hasattr(user.partner_id, '_get_mobile_or_phone'):
                    try:
                        return bool(user.partner_id._get_mobile_or_phone())
                    except:
                        pass
                # Fallback: akses phone langsung dengan safe access
                return bool(getattr(user.partner_id, 'phone', False))
            
            staff_users = all_staff.filtered(_has_phone)[:5]  # Limit untuk menghindari spam
            
            if not staff_users:
                _logger.warning('Tidak ada staff dengan nomor WhatsApp untuk notifikasi dokumen baru')
                return
            
            template = self.env['whatsapp.template'].search([
                ('template_name', '=', 'dokumen_baru_untuk_tandatangan'),
                ('status', '=', 'approved'),
                ('active', '=', True)
            ], limit=1)
            
            if not template:
                _logger.warning('Template WhatsApp "dokumen_baru_untuk_tandatangan" tidak ditemukan')
                return
            
            # Hitung jumlah dokumen pending
            jumlah_pending = self.env['sicantik.document'].search_count([
                ('state', '=', 'pending_signature')
            ])
            
            # Kirim notifikasi ke setiap staff
            for user in staff_users[:5]:  # Limit 5 staff untuk menghindari spam
                try:
                    # Ambil nomor mobile dari partner_id
                    mobile = user.partner_id._get_mobile_or_phone() if user.partner_id else False
                    if not mobile:
                        _logger.warning(f'User {user.name} tidak memiliki nomor mobile/phone')
                        continue
                    
                    # Buat composer
                    composer = self.env['whatsapp.composer'].create({
                        'res_model': self._name,
                        'res_ids': record.ids,
                        'wa_template_id': template.id,
                        'phone': mobile,
                    })
                    
                    # Set free text untuk jumlah dokumen pending
                    composer.free_text_1 = str(jumlah_pending)
                    
                    composer._send_whatsapp_template(force_send_by_cron=True)
                    
                    _logger.info(f'✅ Notifikasi dokumen baru dikirim ke {user.name}')
                    
                except Exception as e:
                    _logger.error(f'❌ Error mengirim notifikasi ke {user.name}: {str(e)}')
    
    def _kirim_notifikasi_perlu_approval(self):
        """
        Kirim notifikasi WhatsApp ke pejabat saat dokumen perlu approval
        Template: approval_required
        """
        for record in self:
            # Cari pejabat berwenang dari workflow (reverse lookup)
            workflow = self.env['signature.workflow'].search([
                ('document_id', '=', record.id),
                ('state', '=', 'pending')
            ], limit=1)
            
            if not workflow or not workflow.approver_id:
                _logger.debug(f'Tidak ada workflow atau approver untuk dokumen {record.document_number}')
                return
            
            approver = workflow.approver_id
            # Ambil nomor mobile dari partner jika approver adalah res.users
            if hasattr(approver, 'partner_id') and approver.partner_id:
                mobile = approver.partner_id._get_mobile_or_phone()
            elif hasattr(approver, 'mobile'):
                mobile = approver.mobile
            elif hasattr(approver, '_get_mobile_or_phone'):
                mobile = approver._get_mobile_or_phone()
            else:
                mobile = False
            
            if not mobile:
                _logger.warning(f'Pejabat {approver.name} tidak memiliki nomor WhatsApp')
                return
            
            template = self.env['whatsapp.template'].search([
                ('template_name', '=', 'dokumen_perlu_approval'),
                ('status', '=', 'approved'),
                ('active', '=', True)
            ], limit=1)
            
            if not template:
                return
            
            try:
                # Ambil data dokumen untuk variabel template
                permit_type_name = record.permit_type_id.name if record.permit_type_id else 'Tidak diketahui'
                applicant_name = record.permit_id.applicant_name if record.permit_id else 'Tidak diketahui'
                permit_number = record.permit_id.permit_number if record.permit_id and hasattr(record.permit_id, 'permit_number') else record.document_number or 'Tidak ada'
                
                # Buat composer dengan phone manual karena phone_field tidak bisa akses workflow
                composer = self.env['whatsapp.composer'].create({
                    'res_model': self._name,
                    'res_ids': record.ids,
                    'wa_template_id': template.id,
                    'phone': mobile,  # Set phone manual
                })
                
                # Set semua variabel template (semua sekarang menggunakan free_text)
                # {{1}} = Nama pejabat
                composer.free_text_1 = approver.name or 'Pejabat Berwenang'
                # {{2}} = Jenis izin
                composer.free_text_2 = permit_type_name
                # {{3}} = Nama pemohon
                composer.free_text_3 = applicant_name
                # {{4}} = Nomor surat
                composer.free_text_4 = permit_number
                # {{5}} = URL approval
                composer.free_text_5 = f'https://perizinan.karokab.go.id/approval/{workflow.id}'
                
                composer._send_whatsapp_template(force_send_by_cron=True)
                
                _logger.info(f'✅ Notifikasi approval dikirim ke {approver.name}')
                
            except Exception as e:
                _logger.error(f'❌ Error mengirim notifikasi approval: {str(e)}')
                import traceback
                _logger.error(traceback.format_exc())
    
    @api.model
    def cron_reminder_dokumen_pending(self):
        """
        Cron job untuk reminder dokumen yang pending lebih dari 24 jam
        Dijalankan setiap hari jam 10:00
        """
        _logger.info('='*80)
        _logger.info('⏰ CRON: Reminder dokumen pending')
        _logger.info('='*80)
        
        # Cari dokumen yang pending lebih dari 24 jam
        threshold_time = datetime.now() - timedelta(hours=24)
        
        dokumen_pending = self.search([
            ('state', '=', 'pending_signature'),
            ('write_date', '<', threshold_time)
        ])
        
        if not dokumen_pending:
            _logger.info('Tidak ada dokumen pending lebih dari 24 jam')
            return
        
        template = self.env['whatsapp.template'].search([
            ('template_name', '=', 'reminder_dokumen_pending'),
            ('status', '=', 'approved'),
            ('active', '=', True)
        ], limit=1)
        
        if not template:
            _logger.warning('Template WhatsApp "reminder_dokumen_pending" tidak ditemukan')
            return
        
        # Kirim reminder ke staff
        # Field mobile ada di res.partner, bukan res.users, jadi kita filter manual
        all_staff = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True)
        ])
        
        # Filter manual untuk user yang punya phone di partner_id
        # Di Odoo 18.4, hanya ada field 'phone', tidak ada 'mobile'
        def _has_phone(user):
            if not user.partner_id:
                return False
            # Gunakan method _get_mobile_or_phone() jika ada, atau langsung akses phone
            if hasattr(user.partner_id, '_get_mobile_or_phone'):
                try:
                    return bool(user.partner_id._get_mobile_or_phone())
                except:
                    pass
            # Fallback: akses phone langsung dengan safe access
            return bool(getattr(user.partner_id, 'phone', False))
        
        staff_users = all_staff.filtered(_has_phone)[:3]  # Limit untuk menghindari spam
        
        for user in staff_users[:3]:  # Limit 3 staff
            try:
                # Ambil nomor mobile dari partner_id
                mobile = user.partner_id._get_mobile_or_phone() if user.partner_id else False
                if not mobile:
                    _logger.warning(f'User {user.name} tidak memiliki nomor mobile/phone')
                    continue
                
                # Ambil sample dokumen pending
                sample_doc = dokumen_pending[0]
                
                composer = self.env['whatsapp.composer'].create({
                    'res_model': self._name,
                    'res_ids': sample_doc.ids,
                    'wa_template_id': template.id,
                    'phone': mobile,
                })
                
                # Set free text untuk jumlah dokumen
                composer.free_text_1 = str(len(dokumen_pending))
                
                composer._send_whatsapp_template(force_send_by_cron=True)
                
                _logger.info(f'✅ Reminder dikirim ke {user.name}')
                
            except Exception as e:
                _logger.error(f'❌ Error mengirim reminder: {str(e)}')
        
        _logger.info(f'✅ Total reminder dikirim: {len(staff_users[:3])}')
        _logger.info('='*80)

