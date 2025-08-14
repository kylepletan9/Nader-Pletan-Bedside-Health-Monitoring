# Final Exam Training Code
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score, ConfusionMatrixDisplay, confusion_matrix, roc_curve, auc
from sklearn import svm, datasets
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_curve, auc
from sklearn.preprocessing import label_binarize
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import roc_auc_score

import pandas as pd
import pickle
import matplotlib.pyplot as plt
import numpy as np
from itertools import cycle
from scipy.stats import linregress

# Function to print the unique label values
def print_unique_values(df):
    print("--Showing Unique Values--")
    unique_values = df['Label'].unique()
    for value in unique_values:
        print(value)

# List of file paths from the open tab metadata
file_paths = ["temp1.csv", "temp2.csv", "temp3.csv", "temp4.csv", "temp5.csv"]

# Read CSV data from each file
dfs = []
column_names = ["Value", "Label"]
for file_path in file_paths:
    try:
        df = pd.read_csv(file_path, header=None, names=column_names)
        dfs.append(df)
        print(f"Read data from {file_path}")
    except Exception as e:
        print(f"Error reading data from {file_path}: {str(e)}")

# Concatenate all dataframes into a single dataframe
combined_df = pd.concat(dfs, axis=0, ignore_index=True)

# Features and labels
X = combined_df[['Value']]
y = combined_df['Label']

# Binarize for ROC
classes = sorted(list(set(y)))
y_bin = label_binarize(y, classes=classes)
n_classes = y_bin.shape[1]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
y_bin_train, y_bin_test = train_test_split(y_bin, test_size=0.3, random_state=42)

# Initialize models
model_L = LogisticRegression(max_iter=3000)
model_S = svm.SVC(probability=True)  # Enable predict_proba for ROC
model_R = RandomForestClassifier()

models = {
    'Logistic Regression': model_L,
    'Support Vector': model_S,
    'Random Forest': model_R
}

# Evaluate models and store metrics
metrics = {}

for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    precision = precision_score(y_test, y_pred, average='weighted')
    recall = recall_score(y_test, y_pred, average='weighted')
    f1 = f1_score(y_test, y_pred, average='weighted')
    accuracy = accuracy_score(y_test, y_pred)

    metrics[name] = {
        'model': model,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'accuracy': accuracy
    }

    print(f"\n{name} Metrics:")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1-score: {f1:.4f}")
    print(f"Accuracy: {accuracy:.4f}")

    # Plot confusion matrix for this model
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=['NORMAL','WARNING','CRITICAL'])
    disp.plot(cmap=plt.cm.Blues)
    plt.title(f"Confusion Matrix: {name}")
    plt.show()

    # ROC Curves
    clf = OneVsRestClassifier(model)
    clf.fit(X_train, y_bin_train)
    y_score = clf.predict_proba(X_test)

    fpr = dict()
    tpr = dict()
    roc_auc = dict()

    for i in range(n_classes):
        fpr[i], tpr[i], _ = roc_curve(y_bin_test[:, i], y_score[:, i])
        roc_auc[i] = auc(fpr[i], tpr[i])

    # Plot ROC curves for each class
    plt.figure()
    colors = cycle(['aqua', 'darkorange', 'cornflowerblue', 'darkgreen'])
    for i, color in zip(range(n_classes), colors):
        plt.plot(fpr[i], tpr[i], color=color, lw=2,
                 label=f"ROC curve of class {classes[i]} (AUC = {roc_auc[i]:.2f})")

    plt.plot([0, 1], [0, 1], 'k--', lw=1)
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title(f"ROC Curve: {name}")
    plt.legend(loc="lower right")
    plt.grid()
    plt.show()

# Rank models across all metrics (lower rank sum is IDEAL)
scores = {name: 0 for name in metrics}
for metric_name in ['precision', 'recall', 'f1', 'accuracy']:
    ranked = sorted(metrics.items(), key=lambda x: x[1][metric_name], reverse=True)
    for rank, (name, _) in enumerate(ranked):
        scores[name] += rank

# Add rank score to metrics dictionary
for name in scores:
    metrics[name]['rank_score'] = scores[name]

# Build and print model summary table
summary_table = {
    name: {
        'Precision': m['precision'],
        'Recall': m['recall'],
        'F1-score': m['f1'],
        'Accuracy': m['accuracy'],
        'Total Rank': m['rank_score']
    }
    for name, m in metrics.items()
}

df_summary = pd.DataFrame(summary_table).T.round(4)
print("\nModel Metrics Summary with Rankings:")
print(df_summary.sort_values(by="Total Rank"))

# Select optimal model
optimal_model_name = df_summary['Total Rank'].idxmin()
optimal_model = metrics[optimal_model_name]['model']

print(f"\nSelected Optimal Model: {optimal_model_name}")

# Save and load optimal model
filename = f'{optimal_model_name}_OPTIMAL_MODEL.sav'
pickle.dump(optimal_model, open(filename, 'wb'))
model = pickle.load(open(filename, 'rb'))