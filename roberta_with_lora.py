# -*- coding: utf-8 -*-
"""roberta_full_finetuning.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1okiOde35eZovD4CJTERS9kk9ptVtTQe_
"""

import torch
from torch import cuda
from datasets import load_dataset
from transformers import AutoTokenizer, RobertaForSequenceClassification, Trainer, TrainingArguments
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score
from transformers import TrainerCallback
from peft import LoraConfig, get_peft_model, TaskType
import pickle

device = 'cuda' if cuda.is_available() else 'cpu'

print(device)

tokenizer = AutoTokenizer.from_pretrained("roberta-base")
model = RobertaForSequenceClassification.from_pretrained("roberta-base").to(device)

ds = load_dataset("stanfordnlp/sst2")

def tokenize(batch):
    return tokenizer(batch['sentence'], padding='max_length', truncation=True)
ds = ds.map(tokenize, batched=True)
ds.set_format(type='torch', columns=['input_ids', 'attention_mask', 'label'])

train_ds = ds['train']
train_test_split = train_ds.train_test_split(test_size=0.2)
train_ds = train_test_split['train']
test_ds = train_test_split['test']
val_ds = ds['validation']

print(len(train_ds))
print(len(test_ds))
print(len(val_ds))

train_acc = []
class TrainAccCallback(TrainerCallback):
    def on_epoch_end(self, args, state, control, **kwargs):
        # Perform a prediction on the training set
        train_predictions = trainer.predict(train_ds)
        train_preds = train_predictions.predictions.argmax(axis=-1)
        train_labels = train_predictions.label_ids
        train_accuracy = accuracy_score(train_labels, train_preds)
        train_acc.append(train_accuracy)
        print(f"Training Accuracy after epoch {state.epoch}: {train_accuracy:.4f}")

training_args = {
    "output_dir": "./output",
    "overwrite_output_dir": True,
    "num_train_epochs": 4,
    "per_device_train_batch_size": 16,
    "per_device_eval_batch_size": 16,
    "learning_rate": 1e-5,
    "weight_decay": 0.01,
    "load_best_model_at_end": True,
    "metric_for_best_model": "accuracy",
    "evaluation_strategy": "epoch",
    "save_strategy": "epoch",
    "logging_strategy": "epoch",
}

peft_config = LoraConfig(
    task_type=TaskType.SEQ_CLS,
    r=8,
    lora_alpha=32,
    lora_dropout=0.1,
    target_modules=["query", "key", "value"]
)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = logits.argmax(axis=-1)
    return {"accuracy": accuracy_score(labels, predictions)}

model = get_peft_model(model, peft_config)
model.print_trainable_parameters()

training_args = TrainingArguments(**training_args)
trainer = Trainer(model=model, args=training_args, train_dataset=train_ds, eval_dataset=val_ds, compute_metrics=compute_metrics, callbacks=[TrainAccCallback()])

res = trainer.train(resume_from_checkpoint=True)
trainer.save_model("./best_roberta_model")

trainer.evaluate()

test_results = trainer.evaluate(eval_dataset=test_ds, metric_key_prefix="test")

log_history = trainer.state.log_history


val_acc = [entry['eval_accuracy'] for entry in log_history if 'eval_accuracy' in entry]


log_history_file = 'log_history.pkl'
with open(log_history_file, 'wb') as f:
    pickle.dump(log_history, f)

print(train_acc)
print(val_acc)
n = 4
epochs = [i for i in range(1,n+1)]


plt.plot(epochs, train_acc, label='Accuracy (Train)')
plt.plot(epochs, val_acc, label='Accuracy (Val)')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.title('Training and Validation Accuracy')
plt.legend()
plt.savefig('roberta_with_lora.png')


print(test_results["test_accuracy"])