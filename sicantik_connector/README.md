# SICANTIK Connector Module

## Overview

SICANTIK Connector is an Odoo 18 module that integrates with SICANTIK (Sistem Informasi Perizinan Kabupaten Karo) to provide:

- **API Integration** with production SICANTIK server
- **Automated Data Synchronization** for permits and permit types
- **Expiry Date Monitoring** with WhatsApp notifications
- **Dashboard and Statistics** for permit management
- **Comprehensive Logging** and error handling

## Features

### Core Features
- ✅ API configuration and connection testing
- ✅ Automated permit synchronization
- ✅ Permit type master data management
- ✅ Partner integration with WhatsApp support
- ✅ Expiry date tracking and notifications

### Expiry Sync (Workaround Solution)
- ✅ Two-step API process for expiry dates
- ✅ Rate limiting (10 requests/second)
- ✅ Progress tracking (every 50 permits)
- ✅ Error handling and retry logic
- ✅ Performance monitoring

### Cron Jobs
- **00:00 AM** - Update expired permits status
- **02:00 AM** - Sync expiry dates (workaround)
- **09:00 AM** - Check expiring permits & send notifications

## Installation

1. Copy this module to your Odoo addons directory:
   ```bash
   cp -r sicantik_connector /path/to/odoo/addons/
   ```

2. Update apps list in Odoo:
   - Go to Apps menu
   - Click "Update Apps List"

3. Install the module:
   - Search for "SICANTIK Connector"
   - Click "Install"

## Configuration

### Initial Setup

1. Go to **SICANTIK > Configuration > API Configuration**
2. The default configuration is automatically created
3. Click "Test Connection" to verify API access
4. Adjust settings as needed:
   - API URL (default: https://perizinan.karokab.go.id/backoffice/api)
   - Timeout (default: 30 seconds)
   - Sync interval (default: 15 minutes)
   - Rate limiting (default: 10 req/sec)

### First Sync

1. Go to **SICANTIK > Configuration > API Configuration**
2. Click "Sync Now" to fetch initial data
3. Check **SICANTIK > Permits** to see synced permits

### Expiry Sync

1. Go to **SICANTIK > Configuration > API Configuration**
2. Click on the connector record
3. Click "Sync All Expiry Dates"
4. Choose to test with 10 permits or sync all
5. Monitor progress in server logs

## Usage

### View Permits

1. Go to **SICANTIK > Permits**
2. Use filters:
   - Active permits
   - Expired permits
   - Critical (≤30 days)
   - Warning (≤60 days)
   - Without expiry date

### View Permit Types

1. Go to **SICANTIK > Permit Types**
2. Click on a type to see statistics
3. Click "View Permits" to see permits of that type

### Manual Sync

1. Go to **SICANTIK > Configuration > API Configuration**
2. Click "Sync Now" for immediate synchronization

### Test Expiry Sync

1. Open any connector record
2. Click "Test Expiry Sync" button
3. This will sync 10 permits for testing

## Technical Details

### Dependencies
- `base` - Core Odoo functionality
- `mail` - For messaging and logging

### External Libraries
- `requests` - For API calls
- `base64` - For encoding
- Standard Python libraries

### API Endpoints Used
- `/jumlahPerizinan` - Test connection
- `/listpermohonanterbit` - Get permits
- `/cekperizinan` - Get permit details (workaround)
- `/jenisperizinanlist` - Get permit types

### Performance

**Workaround Solution:**
- ~0.15 seconds per permit
- 500 permits = ~75 seconds
- Rate limited to 10 req/sec
- Progress logged every 50 permits

**After API Update (Future):**
- Expected: 100x faster
- 500 permits = ~0.75 seconds

## Troubleshooting

### Connection Issues

**Problem:** "Connection timeout"
**Solution:** 
- Check internet connection
- Verify API URL is correct
- Increase timeout in configuration

**Problem:** "Connection error"
**Solution:**
- Verify SICANTIK server is accessible
- Check firewall settings
- Test API URL in browser

### Sync Issues

**Problem:** "No permits synced"
**Solution:**
- Check API configuration is active
- Verify API returns data
- Check server logs for errors

**Problem:** "Expiry sync slow"
**Solution:**
- This is expected with workaround
- Use max_permits parameter for testing
- Wait for API update for optimization

### Cron Job Issues

**Problem:** "Cron jobs not running"
**Solution:**
- Check cron jobs are active
- Verify Odoo cron worker is running
- Check server logs for errors

## Migration Path

### Current (Workaround)
- Using two-step API process
- Performance: ~0.15s per permit
- Functional but not optimal

### Future (After API Update)
1. Pemkab updates API to include `d_berlaku_izin`
2. Remove workaround code
3. Deploy optimized solution
4. Performance: 100x faster

## Support

For issues or questions:
- Check server logs: `/var/log/odoo/odoo-server.log`
- Enable debug mode for detailed logs
- Contact SICANTIK Development Team

## License

LGPL-3

## Author

SICANTIK Development Team

## Version

1.0.0 - Initial Release

## Changelog

### 1.0.0 (2025-10-29)
- Initial release
- Core API integration
- Permit and permit type management
- Expiry sync workaround implementation
- Cron jobs for automation
- Dashboard and statistics
- Partner integration
- WhatsApp notification hooks

