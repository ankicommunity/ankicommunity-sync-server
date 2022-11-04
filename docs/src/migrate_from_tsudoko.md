## Migrate Data from Tsudoko's anki-sync-server

This project continues on from tsudoko's work. I believe there's been no changes to the data store since the tsudoko's version as such you can update the server code and have everything work as it should.

1. Make a copy for the data of cards[configued in the ankisyncd.conf].

2. Uninstall the old version[tsudoko] and install the one provided by ankicommunity.

3. Update the ankisyncd.conf, change it's data_root to the copy's path in step 1.

4. Add a user as same as the older one.

5. Restart the service.

6. Sync data, choose either side you want to keep.

If you have any issues, please feel free to raise it in this ticket: https://github.com/ankicommunity/anki-sync-server/issues/96.