#/bin/bash
source env/bin/activate
exec flask cron update_courses >> cron.log 2>&1
