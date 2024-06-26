# -*- coding: utf-8 -*-
"""RougeplotResult.ipynb

Automatically generated by Colaboratory.

"""

from google.colab import drive

drive.mount('/content/drive')
file_path = #

!pip install --quiet datasets
!pip install --quiet transformers datasets torch
!pip install --quiet transformers[torch]
!pip install --quiet accelerate -U
!pip install --quiet tqdm

from transformers import T5ForConditionalGeneration, T5Tokenizer, AutoTokenizer, AutoModelForSeq2SeqLM
from datasets import load_dataset
import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm
import numpy as np
from torch.optim import AdamW
from torch.nn import CrossEntropyLoss
import torch.nn.functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

base_model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")
base_model.to(device)
tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-large")

teacher_model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-large")
teacher_model = teacher_model.to(device)

teacher_model.to("cpu")
# Apply dynamic quantization (note: T5 may have limited support for dynamic quantization beyond Linear layers)
quantized_model = torch.quantization.quantize_dynamic(
    teacher_model, {torch.nn.Linear}, dtype=torch.qint8
)
teacher_model.to(device)

student_model_025 = AutoModelForSeq2SeqLM.from_pretrained(file_path +'/student_model_025').to(device)
student_model_05 = AutoModelForSeq2SeqLM.from_pretrained(file_path +'/student_model_05').to(device)
student_model_075 = AutoModelForSeq2SeqLM.from_pretrained(file_path +'/student_model_075').to(device)
student_model_one = AutoModelForSeq2SeqLM.from_pretrained(file_path +'/student_model_one').to(device)

loss_model_025 = torch.load(file_path + '/loss_list_025.pt')
loss_model_05 = torch.load(file_path + '/loss_list_05.pt')
loss_model_075 = torch.load(file_path + '/loss_list_075.pt')
loss_model_one = torch.load(file_path + '/loss_list_one.pt')

import matplotlib.pyplot as plt

# Plotting the combined loss curves for all models
plt.figure(figsize=(12, 8))

# Plotting each loss curve and setting labels for legends
plt.plot(loss_model_025, label='Model 0.25', marker='o', linestyle='-')
plt.plot(loss_model_05, label='Model 0.5', marker='o', linestyle='-')
plt.plot(loss_model_075, label='Model 0.75', marker='o', linestyle='-')
plt.plot(loss_model_one, label='Model 1.0', marker='o', linestyle='-')

# Plotting a general legend for all the curves
plt.title("Loss Curve Across Different Alpha with an Epoch Size of 4")
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.legend()
plt.show()

# Prepare and tokenize the dataset
def tokenize_and_format(examples):
    # Tokenizing the input texts
    tokenized_inputs = tokenizer(examples['input_text'], padding="max_length", truncation=True, max_length=512)
    # Tokenizing the target texts
    tokenized_targets = tokenizer(examples['target_text'], padding="max_length", truncation=True, max_length=512)

    return {
        'input_ids': tokenized_inputs.input_ids,
        'attention_mask': tokenized_inputs.attention_mask,
        'labels': tokenized_targets.input_ids
    }

# Load and preprocess dataset
eval_dataset = load_dataset("Nicolas-BZRD/Parallel_Global_Voices_English_French", split="train")

eval_dataset = eval_dataset.select(range(10000,12000))
eval_dataset = eval_dataset.map(lambda example: {'input_text': ["translate English to French: " + ex for ex in example["en"]],
                                                  'target_text': example["fr"]},
                                batched=True)
eval_dataset = eval_dataset.map(tokenize_and_format, batched=True)

eval_dataset.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])
eval_dataloader = DataLoader(eval_dataset, batch_size=16, shuffle=False)

from tqdm.auto import tqdm

# List to store predictions for each model
teacher_predictions, student_025_predictions, student_05_predictions, student_075_predictions, student_one_predictions, base_predictions = [], [], [], [], [], []

# Assuming all models are loaded and set to the correct device

# Set all models to evaluation mode
teacher_model.eval()
student_model_025.eval()
student_model_05.eval()
student_model_075.eval()
student_model_one.eval()
base_model.eval()

# Loop through data for all models
for batch in tqdm(eval_dataloader, desc="Generating predictions for all models"):
    input_ids, attention_mask = batch['input_ids'].to(device), batch['attention_mask'].to(device)

    with torch.no_grad():
        # Teacher model predictions
        teacher_outputs = teacher_model.generate(input_ids=input_ids, attention_mask=attention_mask)
        # Student model predictions
        student_025_outputs = student_model_025.generate(input_ids=input_ids, attention_mask=attention_mask)
        student_05_outputs = student_model_05.generate(input_ids=input_ids, attention_mask=attention_mask)
        student_075_outputs = student_model_075.generate(input_ids=input_ids, attention_mask=attention_mask)
        student_one_outputs = student_model_one.generate(input_ids=input_ids, attention_mask=attention_mask)
        # Base model predictions
        base_outputs = base_model.generate(input_ids=input_ids, attention_mask=attention_mask)

    # Decode the generated ids to text for all models
    teacher_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in teacher_outputs]
    student_025_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_025_outputs]
    student_05_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_05_outputs]
    student_075_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_075_outputs]
    student_one_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_one_outputs]
    base_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in base_outputs]

    # Extend predictions for all models
    teacher_predictions.extend(teacher_preds)
    student_025_predictions.extend(student_025_preds)
    student_05_predictions.extend(student_05_preds)
    student_075_predictions.extend(student_075_preds)
    student_one_predictions.extend(student_one_preds)
    base_predictions.extend(base_preds)

from datasets import load_metric

# Load the ROUGE metric
rouge = load_metric("rouge")

# Printing the results
#print("ROUGE-1:", results['rouge1'].mid)  # mid contains the f-measure, precision, and recall as a Score object
#print("ROUGE-2:", results['rouge2'].mid)
#print("ROUGE-L:", results['rougeL'].mid)

# Prepare candidates: Student models predictions as simple lists of strings
student_models = {
    "base": base_predictions,
    "student_025B": student_025_predictions,
    "student_05B": student_05_predictions,
    "student_075B": student_075_predictions,
    "student_oneB": student_one_predictions
}

# Dictionary to store BERTScore results for each student model
student_rougeL_scores = {}

references = [ref.split() for ref in teacher_predictions]  # Teacher predictions as reference

for model_name, predictions in student_models.items():
    # Compute ROUGE
    # Note: The ROUGE metric expects a list of predictions and a list of references (each reference itself being a list)
    rouge_result = rouge.compute(predictions=predictions, references=[[ref] for ref in references])
    student_rougeL_scores[model_name] = rouge_result["rougeL"].mid.fmeasure

# Display the results
for model_name, rouge_l_f1 in student_rougeL_scores.items():
    print(f"{model_name.capitalize()} Model ROUGE-1 F1 Score: {rouge_l_f1:.4f}")

quant_predictions_file = '/content/drive/My Drive/cse417/projectFinal/quant_predictions.txt'
# Function to load predictions from a file
def load_predictions(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f]
quant_predictions = load_predictions(quant_predictions_file)

print(quant_predictions)

bertscore_result = rouge.compute(predictions=quant_predictions, references=[[ref] for ref in references])
a = rouge_result["rougeL"].mid.fmeasure

print(references)

# Model names and their corresponding BLEU scores
models = ['Base Model (Control)', 'Student Model (alpha=0.25)', 'Student Model (alpha=0.5)', 'Student Model (alpha=0.75)', 'Student Model (alpha=1.0)','Quantized']
rouge_score_list = []

# Compute BLEU scores for each model
for model_name, bleu_score in student_rougeL_scores.items():
    rouge_score_list.append(bleu_score)

rouge_score_list.append(a)

# Color list for the bar chart
clist = ['#1f77b4', '#60a3d9', '#a3d2f5', '#4e79a7', '#93c7e4','#78c679']

# Plotting
plt.figure(figsize=(10, 6))
plt.bar(models, rouge_score_list, color=clist)
plt.ylabel('ROUGE F1 Score')
plt.title('Comparison of ROUGE-L F1 Score in English-to-French Translation')
#plt.ylim(0, 0.5)  # BLEU scores range from 0 to 1

# Rotate x-axis labels
plt.xticks(rotation=45, ha='right')

# Adjust layout to prevent clipping of labels
plt.tight_layout()

# Display the plot
plt.show()

# actual vaules of BLEU scores -> quantized took me 48 minutes while others took me about 15seconds with batch size of 16
print(rouge_score_list)

def tokenize_and_format2(examples):
    # Tokenizing the input texts
    tokenized_inputs = tokenizer(examples['input_text'], padding="max_length", truncation=True, max_length=512)
    # Tokenizing the target texts
    tokenized_targets = tokenizer(examples['target_text'], padding="max_length", truncation=True, max_length=512)

    return {
        'input_ids': tokenized_inputs.input_ids,
        'attention_mask': tokenized_inputs.attention_mask,
        'labels': tokenized_targets.input_ids
    }

# Load and preprocess dataset
test_dataset = load_dataset("Nicolas-BZRD/Parallel_Global_Voices_English_French", split="train")

test_dataset = test_dataset.select(range(12000,13000))
test_dataset = test_dataset.map(lambda example: {'input_text': ["translate French to English: " + ex for ex in example["fr"]],
                                                  'target_text': example["en"]},
                                batched=True)
test_dataset = test_dataset.map(tokenize_and_format2, batched=True)

test_dataset.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])
test_dataloader = DataLoader(test_dataset, batch_size=16, shuffle=False)

from tqdm.auto import tqdm

# List to store predictions for each model
teacher_OOD, student_025_OOD, student_05_OOD, student_075_OOD, student_one_OOD, base_OOD = [], [], [], [], [], []

# Assuming all models are loaded and set to the correct device

# Set all models to evaluation mode
teacher_model.eval()
student_model_025.eval()
student_model_05.eval()
student_model_075.eval()
student_model_one.eval()
base_model.eval()

# Loop through data for all models
for batch in tqdm(test_dataloader, desc="Generating predictions for all models"):
    input_ids, attention_mask = batch['input_ids'].to(device), batch['attention_mask'].to(device)

    with torch.no_grad():
        # Teacher model predictions
        teacher_outputs = teacher_model.generate(input_ids=input_ids, attention_mask=attention_mask)
        # Student model predictions
        student_025_outputs = student_model_025.generate(input_ids=input_ids, attention_mask=attention_mask)
        student_05_outputs = student_model_05.generate(input_ids=input_ids, attention_mask=attention_mask)
        student_075_outputs = student_model_075.generate(input_ids=input_ids, attention_mask=attention_mask)
        student_one_outputs = student_model_one.generate(input_ids=input_ids, attention_mask=attention_mask)
        # Base model predictions
        base_outputs = base_model.generate(input_ids=input_ids, attention_mask=attention_mask)

    # Decode the generated ids to text for all models
    teacher_OOD_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in teacher_outputs]
    student_025_OOD_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_025_outputs]
    student_05_OOD_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_05_outputs]
    student_075_OOD_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_075_outputs]
    student_one_OOD_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in student_one_outputs]
    base_OOD_batch = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in base_outputs]

    # Extend OOD for all models
    teacher_OOD.extend(teacher_OOD_batch)
    student_025_OOD.extend(student_025_OOD_batch)
    student_05_OOD.extend(student_05_OOD_batch)
    student_075_OOD.extend(student_075_OOD_batch)
    student_one_OOD.extend(student_one_OOD_batch)
    base_OOD.extend(base_OOD_batch)

from datasets import load_metric
rouge = load_metric('rouge')

# Prepare candidates: Student models OOD
student_models_OOD = {
    "base": base_OOD,
    "student_025B": student_025_OOD,
    "student_05B": student_05_OOD,
    "student_075B": student_075_OOD,
    "student_oneB": student_one_OOD
}

student_rougeL_scores = {}

references = [ref.split() for ref in teacher_OOD]  # Teacher OOD as reference

for model_name, predictions in student_models_OOD.items():
    # Compute ROUGE
    # Note: The ROUGE metric expects a list of predictions and a list of references (each reference itself being a list)
    rouge_result = rouge.compute(predictions=predictions, references=[[ref] for ref in references])
    student_rougeL_scores[model_name] = rouge_result["rougeL"].mid.fmeasure

# Display the results
for model_name, rouge_l_f1 in student_rougeL_scores.items():
    print(f"{model_name.capitalize()} Model ROUGE-1 F1 Score: {rouge_l_f1:.4f}")

quant_predictions_k = []

quantized_model.to('cpu')
quantized_model.eval()

# Loop for the quantized model (CPU execution)
for batch in tqdm(test_dataloader, desc="Generating predictions for Quantized model"):
    input_ids, attention_mask = batch['input_ids'].to('cpu'), batch['attention_mask'].to('cpu')

    with torch.no_grad():
        # Quantized model predictions
        quant_outputs = quantized_model.generate(input_ids=input_ids, attention_mask=attention_mask)

    quant_preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in quant_outputs]

    quant_predictions_k.extend(quant_preds)

def save_predictions(predictions, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        for prediction in predictions:
            f.write(prediction + '\n')

file_path = '/content/drive/My Drive/cse417/projectFinal'
quant_predictions_file = f'{file_path}/quant_predictionsFR.txt'  # For quantized model predictions
save_predictions(quant_predictions_k, quant_predictions_file)

# Function to load predictions from a file
def load_predictions(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f]

file_path = '/content/drive/My Drive/cse417/projectFinal'
quant_predictions_file = f'{file_path}/quant_predictionsFR.txt'  # For quantized model predictions
quant_predictions_k = load_predictions(quant_predictions_file)

bleu_result2 = rouge.compute(predictions=quant_predictions_k, references=[[ref] for ref in references])
a2 = bleu_result2["rougeL"].mid.fmeasure

# Model names and their corresponding BLEU scores
models = ['Base Model (Control)', 'Student Model (alpha=0.25)', 'Student Model (alpha=0.5)', 'Student Model (alpha=0.75)', 'Student Model (alpha=1.0)','Quantized']
rouge_score_list = []

# Compute BLEU scores for each model
for model_name, bleu_score in student_rougeL_scores.items():
    rouge_score_list.append(bleu_score)

rouge_score_list.append(a2)

# Color list for the bar chart
clist = ['#1f77b4', '#60a3d9', '#a3d2f5', '#4e79a7', '#93c7e4','#78c679']

# Plotting
plt.figure(figsize=(10, 6))
plt.bar(models, rouge_score_list, color=clist)
plt.ylabel('ROUGE F1 Score')
plt.title('Comparison of ROUGE-L F1 Score in French to English (OOD) Translation')
#plt.ylim(0, 0.5)  # BLEU scores range from 0 to 1

# Rotate x-axis labels
plt.xticks(rotation=45, ha='right')

# Adjust layout to prevent clipping of labels
plt.tight_layout()

# Display the plot
plt.show()

