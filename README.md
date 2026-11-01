# Live Email Spam Detector

Reads new Gmail messages (read-only), classifies them with a fine-tuned DistilBERT model, and shows
spam probability, suspicious signals (SPF/DKIM fail, reply-to mismatch, shortened links) on a live dashboard.

```
Gmail API -> fetcher (poll) -> parser (MIME/HTML cleanup) -> DistilBERT -> SQLite -> Streamlit dashboard
```

## History

This project started in 2022 as a TF-IDF spam classifier. In 2026 it was rebuilt around a
fine-tuned DistilBERT model, with the Gmail connection, header checks (SPF, DKIM, reply-to
mismatch, shortened links) and the live dashboard added.

## Results

Fine-tuned on Enron-Spam, the model reached **99.2% accuracy** and **ROC-AUC 0.9995** on a
held-out test set of 2,000 emails.

These numbers come from the Enron-Spam test split, an older collection of emails. Today's spam
and your own inbox may look different, so expect lower accuracy there. The "Correct / Wrong"
buttons on the dashboard record where it makes mistakes.

## 1. Train the model
Run `email_spam_distilbert_colab.ipynb` on Google Colab (T4 GPU). It saves the model to Drive.
Download the folder `email-spam-distilbert` and place it in `models/`.

## 2. Gmail setup (one time)
1. Open https://console.cloud.google.com and create a project.
2. APIs & Services > Library > enable **Gmail API**.
3. APIs & Services > OAuth consent screen > External > add **your own Gmail address as a Test user**.
4. Credentials > Create credentials > **OAuth client ID** > Application type **Desktop app**.
5. Download the JSON, rename it `credentials.json`, put it in the project root.

`credentials.json` and `token.json` are in `.gitignore`. Never commit them.
The app only requests the **read-only** scope.

## 3. Run
```bash
python -m venv venv && venv\Scripts\activate      # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt

python -m src.fetcher        # terminal 1: first run opens a browser to sign in
streamlit run app.py         # terminal 2: dashboard
```

## Project layout
```
src/config.py        settings (paths, threshold, poll interval)
src/gmail_client.py  OAuth + Gmail API calls
src/email_parser.py  MIME/HTML parsing, links, header signals
src/classifier.py    model loading + prediction
src/db.py            SQLite storage + user feedback
src/fetcher.py       polling loop
app.py               Streamlit dashboard
```

## Roadmap
- Hybrid features (link count, header signals) fed into the model
- Explanations (SHAP/LIME), retraining from "Wrong" feedback
- Demo mode with sample emails for public hosting
<img width="1917" height="973" alt="Untitled Design" src="https://github.com/user-attachments/assets/69120149-9e7a-4b4d-9a2b-b650b8d0e6b9" />
