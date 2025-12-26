# Quick Start: Scheduler

## Step 1: Test the Scheduler

Before scheduling real posts, run the diagnostic to check everything:

```bash
python test_scheduler.py
```

This will tell you:
- ✓ If your database connection works
- ✓ Current scheduled posts
- ✓ Which posts are ready to run
- ✓ Any configuration issues

## Step 2: Schedule a Test Post

1. **Open your browser**: `http://localhost:5001`
2. **Go to Schedule tab**
3. **Fill the form**:
   - Listing: Pick any vehicle
   - Profile: Pick any active profile
   - Date/Time: Set to 2-3 minutes from now (uses YOUR LOCAL TIME!)
   - Recurrence: One Time
4. **Click "Schedule Post"**

## Step 3: Start the Scheduler

In the Schedule tab:
1. Find the "Scheduler Service" card
2. Click **"Start Scheduler"** button
3. You should see:
   - Green spinner animation
   - "Running" status
   - Next scheduled post details

## Step 4: Monitor Execution

### Option A: Watch in Browser
- Refresh the Schedule tab every 30 seconds
- Watch status change: pending → running → completed

### Option B: Watch Logs
Open PowerShell and run:
```powershell
# Watch scheduler log
Get-Content scheduler.log -Wait
```

In another PowerShell window:
```powershell
# Watch bot execution (once it starts)
Get-Content bot_execution.log -Wait
```

## Step 5: Verify Results

After execution:
1. **Schedule tab**: Status should be "completed" or "failed"
2. **History tab**: Should show the execution record
3. **Bot Activities tab**: Should show statistics updated

## What to Expect

### Timeline:
- **T+0**: Post scheduled, status = "pending"
- **T+0 to T+1min**: Scheduler checks, finds nothing yet
- **T+2min**: Scheduled time arrives
- **T+2min to T+3min**: Scheduler detects post, status → "running"
- **T+3min to T+10min**: Bot executes, posts to Facebook
- **T+10min**: Execution complete, status → "completed"

### In scheduler.log:
```
Scheduler Service Started
Checking for posts due before: 2025-12-26T12:00:00
Found 1 pending post(s)
  Post #1: scheduled for 2025-12-26T11:58:00
Executing scheduled post ID: 1
Successfully executed scheduled post #1
```

### In bot_execution.log:
```
FB MARKETPLACE BOT - STARTING
Profiles: 1
Listings: 1
Processing profile: Profile 6
Processing listing: 2020 Honda Civic
✓ Posted successfully
```

## Troubleshooting

### Nothing happens after scheduled time

**Run diagnostic:**
```bash
python test_scheduler.py
```

**Check if scheduler is running:**
- Look at Schedule tab - should show "Running"
- Check `scheduler.log` exists and has recent entries

**Common fixes:**
1. Click "Stop Scheduler" then "Start Scheduler" again
2. Delete the scheduled post and create a new one
3. Make sure time is in the future (uses your local machine time)

### Post stays "pending"

This usually means:
- Scheduler isn't running → Click "Start Scheduler"
- Time is in past → Reschedule for future time
- Database issue → Run `python test_scheduler.py`

### Post changes to "failed"

Check the error:
1. In Schedule tab, hover over failed post to see error message
2. Check `scheduler.log` for details
3. Check `bot_execution.log` for bot errors

Common failures:
- Missing profile path
- Missing location
- Bot dependencies not installed
- Facebook login expired

## Next Steps

Once the test post works:

1. **Schedule recurring posts**
   - Use "Daily", "Weekly", or "Monthly" recurrence
   - Bot will automatically reschedule after each run

2. **Schedule multiple posts**
   - Different listings on different profiles
   - Stagger times to avoid rate limits

3. **Keep scheduler running**
   - Leave it running in background
   - It will execute posts automatically

4. **Monitor regularly**
   - Check Schedule tab daily
   - Review History tab weekly
   - Check logs if issues arise

## Tips

✓ **Schedule during off-peak hours** for better Facebook performance
✓ **Space out posts** - Don't post too frequently
✓ **Test with one post first** before scheduling many
✓ **Monitor the first few runs** to ensure everything works
✓ **Keep profiles active** - Relogin if Facebook sessions expire
