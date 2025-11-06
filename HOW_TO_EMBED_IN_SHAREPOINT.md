# How to Embed Streamlit App in SharePoint

**Quick Guide:** Embed your Streamlit web app in your SharePoint page.

---

## 📋 **Prerequisites**

1. ✅ **Streamlit app deployed** on Streamlit Cloud (or your server)
2. ✅ **SharePoint edit permissions** on the page
3. ✅ **App URL** (e.g., `https://amazon-settlement-transformer.streamlit.app`)

---

## 🚀 **Step-by-Step Instructions**

### **Step 1: Get Your Streamlit App URL**

After deploying to Streamlit Cloud, you'll get a URL like:
```
https://amazon-settlement-transformer.streamlit.app
```

**Copy this URL** - you'll need it in Step 4.

---

### **Step 2: Open Your SharePoint Page**

1. Go to your SharePoint page:
   ```
   https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/SitePages/CollabHome.aspx
   ```

2. **Sign in** if prompted

---

### **Step 3: Edit the Page**

1. Click the **"Edit"** button (usually in the top right)
2. Or click **"Edit"** from the page menu
3. The page will enter edit mode

---

### **Step 4: Add Embed Web Part**

1. **Click the "+" button** where you want to add the app
   - This shows available web parts

2. **Search for "Embed"** or **"Code"**
   - Type: `embed` or `code` in the search box

3. **Select "Embed" web part**
   - Look for "Embed" or "Embed Code" option

---

### **Step 5: Add the Embed Code**

1. **Open the embed code area**
   - You'll see a text box or code editor

2. **Copy this code** (replace `YOUR_APP_URL` with your Streamlit Cloud URL):
   ```html
   <iframe 
       src="YOUR_APP_URL" 
       width="100%" 
       height="800px" 
       frameborder="0"
       style="border: 1px solid #ccc; border-radius: 4px;">
   </iframe>
   ```

3. **Replace `YOUR_APP_URL`** with your actual Streamlit Cloud URL:
   ```html
   <iframe 
       src="https://amazon-settlement-transformer.streamlit.app" 
       width="100%" 
       height="800px" 
       frameborder="0"
       style="border: 1px solid #ccc; border-radius: 4px;">
   </iframe>
   ```

4. **Paste the code** into the embed web part

---

### **Step 6: Save the Page**

1. Click **"Republish"** or **"Save"** (top right)
2. Confirm if prompted
3. **Done!** The app is now embedded

---

## 📱 **Alternative: Direct Link (Simpler)**

If embedding doesn't work, you can add a link instead:

### **Option 1: Link Button**

1. Add a **"Link"** web part
2. Set the link text: "Amazon Settlement Processor"
3. Set the URL: `https://amazon-settlement-transformer.streamlit.app`
4. Check "Open in new tab"
5. Save

### **Option 2: Hyperlink in Text**

1. Edit any text on the page
2. Select text and click "Link" button
3. Add your Streamlit Cloud URL
4. Save

---

## ⚙️ **Customization Options**

### **Adjust Height:**
```html
height="800px"  <!-- Change to 600px, 1000px, etc. -->
```

### **Full Width:**
```html
width="100%"
```

### **Fixed Width:**
```html
width="1200px"
```

### **No Border:**
```html
style="border: none;"
```

### **Custom Styling:**
```html
style="border: 2px solid #0066cc; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
```

---

## 🔍 **Troubleshooting**

### **Issue: "Embed" web part not available**

**Solution:** Use "Embed Code" or "Script Editor" web part instead

### **Issue: App doesn't load**

**Check:**
1. Is the Streamlit app URL correct?
2. Is the app deployed and running?
3. Try opening the URL directly in a browser first

### **Issue: "Content blocked"**

**Solution:** SharePoint may block external content. Try:
- Using a direct link instead of iframe
- Or contact SharePoint admin to allow the domain

### **Issue: App shows blank screen**

**Check:**
1. Open the Streamlit app URL directly in a new tab
2. If it works there, the iframe might be blocked
3. Try using a direct link instead

---

## 📝 **Quick Reference**

### **Embed Code Template:**
```html
<iframe 
    src="YOUR_STREAMLIT_CLOUD_URL" 
    width="100%" 
    height="800px" 
    frameborder="0">
</iframe>
```

### **Your SharePoint Page:**
```
https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/SitePages/CollabHome.aspx
```

### **Your Streamlit App URL:**
```
https://amazon-settlement-transformer.streamlit.app
```
(Replace with your actual URL)

---

## ✅ **After Embedding**

Once embedded, users can:
- ✅ Access the app directly from SharePoint
- ✅ Upload settlement files
- ✅ Process files
- ✅ Download outputs
- ✅ No need to leave SharePoint!

---

**Last Updated:** November 4, 2025  
**Status:** ✅ Ready to Embed



