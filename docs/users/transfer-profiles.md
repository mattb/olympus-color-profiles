# Export and transfer a selected stock profile

Render/profile fitting and file-only planning do not require USB. First export a final stock COLOR or MONO recipe as a profile-bearing JPEG using `profile-jpeg`, inspect it with `profile-info`, and generate `camera-profile-plan`. Use the precise arguments and schemas in the [CLI reference](../CLI-HELP.md); never infer a bank or slot.

Only the explicit physical command writes settings:

```sh
./omrender camera-profile-load /absolute/selected-profile.jpg \
  --bank current --slot 1 --expected-serial YOUR_CAMERA_SERIAL \
  --backup-dir /absolute/new-camera-backup
```

The selected slot belongs to the JPEG's inferred COLOR or MONO family. Use your actual camera identity, not a published example serial. Quit Workspace first, connect the PEN-F using a supported data cable, switch it on and choose Storage when prompted. The native detector may change USB protocol mode before profile identity validation. Keep the backup/result directory and read every outcome before retrying.

An upload can complete without verified readback; a failure can also occur after writing began. Do not assume the camera is unchanged, or retry blindly. A saved backup is not proof of a qualified restore operation. See the [current qualification matrix](../compatibility.md); historical transport experiments do not supersede it.

The stock payload does not set photo WB/exposure. Stock JPEG sharing does not transfer full HSL; it resets destination H/L. With separately chosen unofficial firmware, upload the stock-compatible carrier first, then enter the specified H/L values manually (and S±6/7 manually where needed). This project does not install firmware or provide a complete HSL uploader. Do not infer physical firmware appearance from desktop renders.
