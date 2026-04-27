import os
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.secret_key = "super_secret_fairai_key"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_selection_rates(df, group_col, target_col):
    df[target_col] = pd.to_numeric(df[target_col], errors='coerce').fillna(0)
    stats = []
    groups = df[group_col].dropna().unique()
    for g in groups:
        group_data = df[df[group_col] == g]
        total = len(group_data)
        selected = group_data[target_col].sum()
        rate = selected / total if total > 0 else 0
        stats.append({
            'group': str(g),
            'total': int(total),
            'selected': int(selected),
            'rate': float(rate)
        })
    return pd.DataFrame(stats)

def analyze_bias(df, dataset_type):
    results = {}
    suggestions = []
    
    if dataset_type == 'cv':
        required_cols = ['Gender', 'College', 'Selected']
        for col in required_cols:
            if col not in df.columns:
                return {"error": f"Missing required column: {col}. Uploaded columns: {', '.join(df.columns)}"}
        
        # Gender Bias
        gender_stats = calculate_selection_rates(df, 'Gender', 'Selected')
        results['gender'] = gender_stats.to_dict('records')
        
        # College Bias
        college_stats = calculate_selection_rates(df, 'College', 'Selected')
        results['college'] = college_stats.to_dict('records')
        
        rates = [x['rate'] for x in results['gender']]
        
    elif dataset_type == 'admission':
        required_cols = ['Gender', 'Marks', 'Location', 'Selected']
        for col in required_cols:
            if col not in df.columns:
                return {"error": f"Missing required column: {col}. Uploaded columns: {', '.join(df.columns)}"}
        
        # Gender Bias
        gender_stats = calculate_selection_rates(df, 'Gender', 'Selected')
        results['gender'] = gender_stats.to_dict('records')
        
        # Location Bias
        location_stats = calculate_selection_rates(df, 'Location', 'Selected')
        results['location'] = location_stats.to_dict('records')
        
        rates = [x['rate'] for x in results['gender']]
    
    else:
        return {"error": "Invalid dataset type selected."}

    # Fairness Score (Min / Max rate)
    if not rates or max(rates) == 0:
        fairness_score = 100.0  # Safe fallback if nobody is selected
    else:
        fairness_score = (min(rates) / max(rates)) * 100

    results['fairness_score'] = round(fairness_score, 2)
    
    # Suggestions Engine
    if fairness_score < 60:
        results['status'] = 'Biased ❌'
        suggestions.append("⚠️ Critical: Dataset is highly skewed. Consider balancing your training data.")
        suggestions.append("⚠️ Remove sensitive attributes like 'Gender' during initial screening models.")
        suggestions.append("💡 Introduce standardized evaluation rubrics for all candidates.")
    elif fairness_score < 90:
        results['status'] = 'Moderate ⚠️'
        suggestions.append("⚠️ Mild bias detected in selection rates across demographic groups.")
        suggestions.append("💡 Investigate if other factors (like marks vs college tier) correlate inappropriately.")
        suggestions.append("💡 Regular audits recommended for the ML decision model.")
    else:
        results['status'] = 'Fair ✅'
        suggestions.append("✅ Selection rates appear balanced and fair across evaluated groups.")
        suggestions.append("✅ Model metrics look healthy. Continue monitoring periodically.")
        
    results['suggestions'] = suggestions
    
    # "Before vs After" Simulation Logic (Improvement)
    after_results = []
    if len(rates) > 0:
        overall_sel_rate_target = df['Selected'].mean()
        for r in results['gender']:
            diff = overall_sel_rate_target - r['rate']
            # Boost minority or penalize majority to bridge 85% of the gap
            new_rate = r['rate'] + (diff * 0.85) 
            # Clamp between 0 and 1 just in case
            new_rate = max(0, min(1, new_rate))
            after_results.append({
                'group': r['group'],
                'rate': new_rate,
                'selected': int(r['total'] * new_rate),
                'total': r['total']
            })
    results['after_gender'] = after_results
    
    a_rates = [x['rate'] for x in after_results] if after_results else []
    if not a_rates or max(a_rates) == 0:
        results['after_fairness_score'] = 100.0
    else:
        results['after_fairness_score'] = round((min(a_rates) / max(a_rates)) * 100, 2)
        
    # Formatting for UI status color
    if results['after_fairness_score'] >= 90:
        results['after_status'] = 'Improved ✅'
    elif results['after_fairness_score'] >= 60:
        results['after_status'] = 'Moderate ⚠️'
    else:
        results['after_status'] = 'Biased ❌'
        
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        dataset_type = request.form.get('dataset_type')
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                df = pd.read_csv(filepath)
                results = analyze_bias(df, dataset_type)
                
                if 'error' in results:
                    flash(results['error'], 'error')
                    return redirect(request.url)
                    
                session['analysis_results'] = json.dumps(results)
                session['dataset_type'] = dataset_type
                
                return redirect(url_for('results'))
            except Exception as e:
                flash(f"Error processing file: {str(e)}", 'error')
                return redirect(request.url)
        else:
            flash("Invalid file format. Please upload a CSV file.", 'error')
            return redirect(request.url)
            
    preset_type = request.args.get('type', 'cv')
    return render_template('upload.html', preset_type=preset_type)

@app.route('/results')
def results():
    results_json = session.get('analysis_results')
    if not results_json:
        return redirect(url_for('upload_file'))
        
    analysis_results = json.loads(results_json)
    dataset_type = session.get('dataset_type', 'unknown')
    
    return render_template('results.html', results=analysis_results, dataset_type=dataset_type)

@app.route('/download_sample/<dataset_type>')
def download_sample(dataset_type):
    if dataset_type == 'cv':
        return send_file('data/sample_cv.csv', as_attachment=True)
    elif dataset_type == 'admission':
        return send_file('data/sample_admission.csv', as_attachment=True)
    return "Not found", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
