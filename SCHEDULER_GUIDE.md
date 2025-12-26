# Scheduler Guide

This guide explains how to use the scheduling feature to automate your Facebook Marketplace posts.

## Features

- **Schedule posts** for future execution
- **Recurring posts** - Daily, Weekly, or Monthly
- **Automatic execution** via scheduler service
- **Integration with bot** - Scheduled posts run using the same bot logic
- **Status tracking** - Monitor pending, completed, and failed posts

## How to Use

### 1. Schedule a New Post

1. Go to the **Schedule** tab in the dashboard
2. Fill in the form:
   - **Select Listing**: Choose which vehicle to post
   - **Select Edge Profile**: Choose which Facebook account to use
   - **Schedule Date & Time**: Pick when to post
   - **Recurrence**: Choose one-time, daily, weekly, or monthly
3. Click **Schedule Post**

### 2. Start the Scheduler Service

The scheduler service runs in the background and checks every minute for posts that are due.

1. In the **Schedule** tab, find the "Scheduler Service" card
2. Click **Start Scheduler** button
3. The scheduler will now automatically execute posts when they're due

**Important**: The scheduler must be running for scheduled posts to be executed automatically!

### 3. Monitor Scheduled Posts

- View all scheduled posts in the table
- See the next scheduled post and when it will run
- Check the status of each post (pending, running, completed, failed)

### 4. Manage Scheduled Posts

- **Cancel**: Mark a pending post as cancelled (it won't run)
- **Delete**: Permanently remove a scheduled post

### 5. Stop the Scheduler

- Click **Stop Scheduler** to stop the background service
- Pending posts will remain and can be executed when you restart the scheduler

## Recurrence Options

- **One Time**: Post once at the scheduled time
- **Daily**: Post every day at the same time
- **Weekly**: Post every week on the same day/time
- **Monthly**: Post every 30 days at the same time

After a recurring post executes, it automatically schedules the next run.

## Running the Scheduler Manually (Advanced)

You can also run the scheduler service from the command line:

```bash
python scheduler_service.py
```

To stop it, create a file named `scheduler_stop_signal.txt` in the project directory, or press Ctrl+C.

## Scheduler Logs

The scheduler creates a log file `scheduler.log` with detailed information about:
- When posts are executed
- Success/failure status
- Any errors that occur

## Troubleshooting

### Scheduled posts aren't running

If your scheduled posts stay in "pending" status even after the scheduled time:

1. **Check if scheduler is running**
   - Look for the green "Running" indicator in the Schedule tab
   - If not running, click "Start Scheduler"

2. **Run the diagnostic tool**
   ```bash
   python test_scheduler.py
   ```
   This will show you:
   - All scheduled posts in the database
   - Which posts are due for execution
   - Any validation errors with your posts
   - Current local time vs scheduled times

3. **Check the scheduler log**
   ```bash
   type scheduler.log
   ```
   Look for:
   - "Scheduler Service Started" - confirms it's running
   - "Found X pending post(s)" - shows it's detecting posts
   - Any error messages

4. **Verify scheduled time is correct**
   - Scheduled times use YOUR LOCAL MACHINE TIME (not UTC)
   - Make sure the time is in the future
   - The scheduler checks every 60 seconds with a 2-minute buffer

5. **Check the post status**
   - In the Schedule tab, verify status is "pending" (not "cancelled" or "completed")
   - Refresh the page to see latest status

### Common Issues

**Posts scheduled for the past**
- The scheduler only executes posts scheduled for now or future
- If you missed the time, delete and reschedule the post

**Scheduler not detecting posts**
- Check `scheduler.log` for the message "Checking for posts due before: [time] (Local Time)"
- Compare this time with your scheduled post time
- Times are stored in your local timezone (no timezone conversion)

**Error: "profile_folder not found"**
- Make sure you selected a valid Edge profile when creating the schedule
- The profile must have a location set
- Check Profiles tab to verify the profile exists and is active

**Bot execution fails**
- Check `bot_execution.log` for detailed error messages
- Verify Bot.py and dependencies are installed
- Make sure `selected_profiles.txt` and `selected_listings.csv` are created

**Scheduler keeps stopping**
- Check `scheduler.log` for errors
- Make sure the bot dependencies are installed
- Verify your Supabase credentials are correct in `.env` file
- Don't create `scheduler_stop_signal.txt` file accidentally

### Testing the Scheduler

To test if everything is working:

1. **Schedule a test post**
   - Pick a listing and profile
   - Schedule it for 2-3 minutes in the future
   - Note: Times use your local machine time (what you see is what you get!)

2. **Start the scheduler**
   - Click "Start Scheduler" button
   - Watch the "Scheduler Service" card for status

3. **Monitor the logs**
   ```bash
   # In PowerShell, watch scheduler logs
   Get-Content scheduler.log -Wait

   # In another terminal, watch bot logs (once execution starts)
   Get-Content bot_execution.log -Wait
   ```

4. **Check the results**
   - After the scheduled time, refresh the Schedule tab
   - Status should change from "pending" → "running" → "completed" or "failed"
   - Check History tab for the execution record

5. **Run diagnostic if issues occur**
   ```bash
   python test_scheduler.py
   ```

## Database Schema

The scheduler uses the `scheduled_posts` table with these fields:
- `listing_id`: Which listing to post
- `profile_id`: Which profile to use
- `profile_name`: Profile display name
- `profile_path`: Path to Edge profile folder
- `profile_folder`: Same as profile_path (required for compatibility)
- `location`: Marketplace location
- `scheduled_datetime`: When the post should run
- `next_run_datetime`: Next execution time (for recurring posts)
- `status`: pending, running, completed, failed, cancelled
- `recurrence`: none, daily, weekly, monthly
- `error_message`: Error details if failed

## Tips

1. **Test first**: Schedule a post for 1-2 minutes in the future to test the system
2. **Keep scheduler running**: For reliable automation, keep the scheduler service running
3. **Monitor status**: Check the Schedule tab regularly to ensure posts are executing
4. **Use recurrence wisely**: Avoid posting too frequently to the same groups
5. **Check logs**: Review `scheduler.log` if something goes wrong
