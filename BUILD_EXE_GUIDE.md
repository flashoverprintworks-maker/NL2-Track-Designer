# Getting a real .exe via GitHub (no coding required)

This uses GitHub's free "Actions" service: a real Windows computer in
the cloud that builds the .exe for you. You just upload the folder and
click a button.

## 1. Create a free GitHub account
Go to https://github.com/signup if you don't already have one.

## 2. Create a new repository
- Click the "+" in the top-right corner → "New repository"
- Name it anything, e.g. `nl2-track-designer`
- Set it to **Private** if you'd rather it not be public (that's fine,
  Actions works the same either way)
- Click "Create repository"

## 3. Upload this whole folder
On the new repository's page:
- Click "uploading an existing file"
- Drag the entire `nl2_track_designer` folder's contents in (everything
  inside it, including the `.github` folder — make sure hidden folders
  are included; if your file browser hides folders starting with a dot,
  use the drag-and-drop upload which typically includes them, or use
  GitHub Desktop instead — see the alternative below if this is fiddly)
- Scroll down, click "Commit changes"

**Alternative if drag-and-drop loses the `.github` folder:** install
[GitHub Desktop](https://desktop.github.com/) (a simple app, no command
line), sign in, choose "Add an Existing Repository" pointed at the
`nl2_track_designer` folder, then click "Publish repository".

## 4. Watch it build
- Click the "Actions" tab at the top of your repository
- You should see a workflow run start automatically (it runs on every
  upload). If not, click "Build Windows exe" on the left, then "Run
  workflow"
- Wait 2-5 minutes — it's genuinely building on a real Windows machine

## 5. Download your .exe
- Once it finishes (green checkmark), click into that run
- Scroll down to "Artifacts"
- Download `NL2TrackDesigner-windows-exe` (a .zip containing the .exe)
- Unzip it, and `NL2TrackDesigner.exe` is a real standalone Windows
  program — no Python required to run it, on this PC or any other
  Windows PC.

## Updating it later
Whenever you (or I, giving you new files to upload) change the code,
just upload the new/changed files again and commit — a fresh .exe
builds automatically.

If anything in this process errors out, copy the error message and
share it — GitHub Actions logs are usually specific enough that I can
tell you exactly what to fix.
