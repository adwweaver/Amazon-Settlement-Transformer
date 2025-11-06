# SharePoint Deployment Guide

**How to host the Amazon Settlement Processor on SharePoint**

---

## 🎯 **Overview**

The desktop GUI app (`gui_app.py`) cannot run directly in SharePoint. Instead, we'll use a **Streamlit web application** that can be embedded in SharePoint pages.

---

## 📋 **Option 1: Streamlit Web App (Recommended)**

### **What It Is:**
- Web-based application using Streamlit
- Can be embedded in SharePoint via iframe
- Accessible from any browser
- No local installation needed

### **How to Deploy:**

#### **Step 1: Install Streamlit (if not already installed)**
```bash
pip install streamlit
```

#### **Step 2: Run the Web App Locally (for testing)**
```bash
streamlit run scripts/web_app.py
```

This will start a local server at `http://localhost:8501`

#### **Step 3: Access from SharePoint**

**Option A: Embed in SharePoint Page (Iframe)**

1. **Go to your SharePoint page:**
   ```
   https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/SitePages/CollabHome.aspx
   ```

2. **Edit the page:**
   - Click "Edit" button
   - Add a new "Embed" web part

3. **Add the iframe:**
   ```html
   <iframe src="http://localhost:8501" width="100%" height="800px" frameborder="0"></iframe>
   ```
   
   **Note:** For SharePoint, you'll need to host the Streamlit app on a server. See options below.

**Option B: Direct Link (Simpler)**

1. **Create a SharePoint page:**
   - Go to Site Contents → New → Site Page
   - Name: "Amazon Settlement Processor"

2. **Add a link:**
   - Add a "Link" web part
   - Link to: `http://localhost:8501` (or your server URL)

3. **Users click the link** to open the web app in a new tab

---

## 🚀 **Option 2: Host on Server (For SharePoint Access)**

### **Requirements:**
- A server or computer that's always on
- Accessible from your network or the internet

### **Step 1: Run Streamlit on Server**

On the server computer:
```bash
streamlit run scripts/web_app.py --server.port 8501 --server.address 0.0.0.0
```

### **Step 2: Get Server URL**

- **Local network:** `http://[server-ip]:8501`
- **Internet:** `http://[your-domain]:8501` (requires domain setup)

### **Step 3: Embed in SharePoint**

Use the server URL in the iframe:
```html
<iframe src="http://[server-ip]:8501" width="100%" height="800px" frameborder="0"></iframe>
```

---

## ☁️ **Option 3: Streamlit Cloud (Easiest for SharePoint)**

### **What It Is:**
- Free hosting for Streamlit apps
- Accessible from anywhere
- No server setup needed

### **Step 1: Deploy to Streamlit Cloud**

1. **Push code to GitHub:**
   ```bash
   git add scripts/web_app.py
   git commit -m "Add Streamlit web app"
   git push
   ```

2. **Go to Streamlit Cloud:**
   - Visit: https://share.streamlit.io
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Main file path: `scripts/web_app.py`
   - Click "Deploy"

3. **Get your app URL:**
   ```
   https://[your-app-name].streamlit.app
   ```

### **Step 2: Embed in SharePoint**

1. **Go to your SharePoint page**
2. **Add iframe:**
   ```html
   <iframe src="https://[your-app-name].streamlit.app" width="100%" height="800px" frameborder="0"></iframe>
   ```

**Benefits:**
- ✅ Free hosting
- ✅ Accessible from anywhere
- ✅ No server maintenance
- ✅ Automatic HTTPS

---

## 📱 **Option 4: SharePoint File Library (Simplest)**

### **What It Is:**
- Users upload files to SharePoint
- You process them locally or via automation
- Outputs go back to SharePoint

### **Setup:**

1. **Create SharePoint Libraries:**
   - **Incoming:** Where users upload `.txt` files
   - **Processed:** Where outputs go
   - **Archive:** Historical storage

2. **User Workflow:**
   - Upload file to SharePoint "Incoming" library
   - File is processed (manually or automatically)
   - Outputs appear in "Processed" library
   - User downloads outputs

3. **Automation:**
   - Use `watchdog.py` to monitor SharePoint folder (if synced locally)
   - Or use Power Automate to trigger processing

### **Sync SharePoint Locally:**

1. **Sync SharePoint folder:**
   - Open SharePoint library
   - Click "Sync" button
   - This creates a local folder (e.g., `C:\Users\User\SharePoint\Amazon-ETL\Incoming`)

2. **Update watchdog.py:**
   ```python
   watch_folder = Path(r"C:\Users\User\SharePoint\Amazon-ETL\Incoming")
   ```

3. **Run watchdog:**
   ```bash
   python scripts/watchdog.py --watch-folder "C:\Users\User\SharePoint\Amazon-ETL\Incoming"
   ```

---

## 🎯 **Recommended Approach**

### **For Your Use Case:**

**Best Option: Streamlit Cloud + SharePoint Embed**

1. **Deploy to Streamlit Cloud** (free, 15 minutes)
2. **Embed in SharePoint page** (iframe)
3. **Users access via SharePoint** (no local installation needed)

### **Why This Works:**
- ✅ Accessible from SharePoint
- ✅ No local installation needed
- ✅ Works on any device
- ✅ Free hosting
- ✅ Easy to maintain

---

## 📝 **Step-by-Step: Streamlit Cloud Deployment**

### **1. Prepare Code:**

Ensure `scripts/web_app.py` exists (already created)

### **2. Create `requirements.txt` (if not exists):**

```txt
streamlit>=1.28.0
pandas>=2.0.0
pyyaml>=6.0
openpyxl>=3.1.0
```

### **3. Push to GitHub:**

```bash
git add scripts/web_app.py requirements.txt
git commit -m "Add Streamlit web app for SharePoint"
git push
```

### **4. Deploy to Streamlit Cloud:**

1. Go to: https://share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Select your repository: `Amazon-Settlement-Transformer`
5. Main file path: `scripts/web_app.py`
6. Click "Deploy"

### **5. Get App URL:**

After deployment, you'll get a URL like:
```
https://amazon-settlement-transformer.streamlit.app
```

### **6. Embed in SharePoint:**

1. Go to your SharePoint page:
   ```
   https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/SitePages/CollabHome.aspx
   ```

2. Edit the page

3. Add "Embed" web part

4. Add this HTML:
   ```html
   <iframe 
     src="https://amazon-settlement-transformer.streamlit.app" 
     width="100%" 
     height="800px" 
     frameborder="0"
     style="border: 1px solid #ccc;">
   </iframe>
   ```

5. Save the page

### **7. Access from SharePoint:**

Users can now access the app directly from your SharePoint page!

---

## 🔧 **Configuration for SharePoint**

### **Update Streamlit Config (Optional):**

Create `streamlit/config.toml`:
```toml
[server]
port = 8501
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
```

### **For SharePoint Embedding:**

Streamlit apps work best when embedded if:
- CORS is disabled (for local development)
- XSRF protection is disabled (for iframe embedding)
- The app is publicly accessible (or uses authentication)

---

## 🚨 **Important Notes**

### **File Access:**
- Streamlit Cloud apps can't access local files directly
- You'll need to either:
  - Use file uploads (already implemented)
  - Store files in cloud storage (SharePoint, OneDrive)
  - Use SharePoint API to access files

### **Authentication:**
- Streamlit Cloud free tier: No authentication
- For production: Consider Streamlit Cloud Teams (paid) or self-hosting

### **File Storage:**
- Processed files can be:
  - Downloaded directly from the app
  - Uploaded to SharePoint via API
  - Stored in cloud storage

---

## 📊 **Alternative: SharePoint Power Apps**

If you want a fully integrated SharePoint solution:

1. **Create Power App** (low-code solution)
2. **Connect to SharePoint** libraries
3. **Call Azure Function** for processing
4. **Embed in SharePoint** page

**Pros:**
- Fully integrated with SharePoint
- No external hosting needed
- Native SharePoint experience

**Cons:**
- Requires Power Apps license
- More complex setup
- Less flexible than Streamlit

---

## 🎯 **Quick Start (Recommended)**

1. **Deploy to Streamlit Cloud** (15 minutes)
   - Push code to GitHub
   - Deploy on share.streamlit.io
   - Get your app URL

2. **Embed in SharePoint** (5 minutes)
   - Add iframe to SharePoint page
   - Use your Streamlit Cloud URL

3. **Done!** Users can access from SharePoint

---

**Last Updated:** November 4, 2025  
**Status:** ✅ Ready for Deployment



