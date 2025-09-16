# FM Station Planner - Deployment Guide

## Overview
Complete deployment guide for the FM Station Planner with Gemini Flash API and Telegram bot integration.

## Prerequisites

### API Keys Required
```bash
# In your .env file
GERMINI_FLASH=sk-or-v1-your-openrouter-api-key
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-key
```

## Local Development

### 1. Setup Environment
```bash
# Create virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Test System
```bash
# Test all functionality
python test_gemini.py

# Test offline features
python test_offline.py

# Test location features
python test_location.py
```

### 3. Run Webhook Server
```bash
python webhook_server.py
```

## Production Deployment

### Option 1: Railway (Recommended)

1. **Create Railway Account**: https://railway.app
2. **Connect GitHub**: Link your repository
3. **Deploy**:
   ```bash
   # railway.json (optional)
   {
     "build": {
       "builder": "NIXPACKS"
     },
     "deploy": {
       "startCommand": "python webhook_server.py"
     }
   }
   ```
4. **Set Environment Variables** in Railway dashboard
5. **Get deployment URL**: `https://your-app.railway.app`

### Option 2: Heroku

1. **Create Heroku App**:
   ```bash
   heroku create your-fm-planner-bot
   ```

2. **Create Procfile**:
   ```
   web: python webhook_server.py
   ```

3. **Set Config Variables**:
   ```bash
   heroku config:set GERMINI_FLASH=your-api-key
   heroku config:set TELEGRAM_BOT_TOKEN=your-token
   heroku config:set NEXT_PUBLIC_SUPABASE_URL=your-url
   heroku config:set SUPABASE_SERVICE_ROLE_KEY=your-key
   ```

4. **Deploy**:
   ```bash
   git push heroku main
   ```

### Option 3: Digital Ocean App Platform

1. **Create App** on DigitalOcean
2. **Connect GitHub** repository
3. **Configure**:
   - Build Command: `uv pip install -r requirements.txt`
   - Run Command: `python webhook_server.py`
   - Port: `5000`
4. **Set Environment Variables** in dashboard

## Telegram Bot Setup

### 1. Create Bot with BotFather
```
1. Message @BotFather on Telegram
2. Use /newbot command
3. Choose name: "FM Station Planner Bot"
4. Choose username: "fm_station_planner_bot"
5. Save the bot token
```

### 2. Set Webhook URL
```bash
# After deployment, set webhook
curl -X POST https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook \
     -H "Content-Type: application/json" \
     -d '{"url": "https://your-app.railway.app/webhook/telegram"}'
```

### 3. Test Bot
```bash
# Get bot info
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe

# Check webhook
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

## Mobile App Integration

### Direct API Integration
```python
import requests

# Send location-based request
response = requests.post('https://your-app.railway.app/api/plan-inspection',
    json={
        'latitude': 14.0583,
        'longitude': 100.6014,
        'text': 'หาสถานี FM 10 แห่งใกล้ฉัน'
    }
)

result = response.json()
```

### React Native Example
```javascript
const planInspection = async (latitude, longitude, text) => {
  try {
    const response = await fetch('https://your-app.railway.app/api/plan-inspection', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        latitude,
        longitude,
        text
      })
    });

    const result = await response.json();
    return result.response;
  } catch (error) {
    console.error('Planning error:', error);
  }
};

// Usage with device location
navigator.geolocation.getCurrentPosition(async (position) => {
  const { latitude, longitude } = position.coords;
  const plan = await planInspection(latitude, longitude, 'หาสถานี FM ใกล้ฉัน');
  console.log(plan);
});
```

## Monitoring and Health Checks

### Health Check Endpoint
```bash
# Check system status
curl https://your-app.railway.app/health
```

### Log Monitoring
```bash
# Railway logs
railway logs

# Heroku logs
heroku logs --tail

# Check API costs
# Monitor OpenRouter dashboard for usage
```

## Database Setup (Supabase)

### 1. FM Stations Table
```sql
CREATE TABLE fm_station (
    id SERIAL PRIMARY KEY,
    station_name TEXT NOT NULL,
    frequency DECIMAL(5,2),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    province TEXT,
    district TEXT,
    subdistrict TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX idx_fm_station_province ON fm_station(province);
CREATE INDEX idx_fm_station_location ON fm_station(latitude, longitude);
```

### 2. Sample Data
```sql
INSERT INTO fm_station (station_name, frequency, latitude, longitude, province, district) VALUES
('Radio Thailand Bangkok', 98.5, 13.7563, 100.5018, 'กรุงเทพมหานคร', 'เขตพระนคร'),
('FM 91 BKK', 91.0, 13.7563, 100.5018, 'กรุงเทพมหานคร', 'เขตดุสิต'),
('Cool Fahrenheit 93', 93.0, 13.7563, 100.5018, 'กรุงเทพมหานคร', 'เขตบางรัก');
```

## Security Considerations

### Environment Variables
- Never commit `.env` files
- Use secure environment variable management
- Rotate API keys regularly

### Rate Limiting
- Implement request throttling
- Monitor API usage
- Set up alerts for unusual activity

### Input Validation
- Validate coordinates range
- Sanitize user input
- Implement request size limits

## Cost Optimization

### Gemini Flash Pricing
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens
- Very cost-effective for this use case

### Optimization Tips
- Cache repeated queries
- Optimize prompt lengths
- Monitor usage patterns
- Use appropriate model temperatures

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check GERMINI_FLASH API key
   - Verify OpenRouter account status

2. **Webhook Not Receiving**
   - Verify webhook URL is set correctly
   - Check HTTPS certificate
   - Test with ngrok for local development

3. **Database Connection**
   - Verify Supabase credentials
   - Check service role key permissions
   - Test database connectivity

4. **Location Not Working**
   - Verify GPS permissions
   - Check coordinate validity
   - Test with known coordinates

### Debug Mode
```bash
# Run with debug logging
FLASK_DEBUG=true python webhook_server.py
```

## Performance Optimization

### Caching Strategy
- LLM response caching (1 hour TTL)
- Database query caching
- Location coordinate caching

### Scaling
- Database connection pooling
- Async processing for heavy tasks
- CDN for static resources

## Support

For issues or questions:
1. Check the logs first
2. Test with `test_gemini.py`
3. Verify all environment variables
4. Monitor API quotas and costs

Ready for production deployment with real-time location support! 🚀