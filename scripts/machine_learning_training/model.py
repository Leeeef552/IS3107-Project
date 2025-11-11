from torch.utils.data import Dataset, DataLoader
import torch
import torch.nn.init as init
import torch.nn as nn


# LSTM Model Architecture
class LSTM_Model(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=3, dropout=0.3):
        super(LSTM_Model, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM layer
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
        )
        
        # Simplified output layer
        self.fc = nn.Linear(hidden_size, 1)
        
        # Weight initialization
        for name, param in self.lstm.named_parameters():
            if 'weight_ih' in name:
                init.xavier_uniform_(param)
            elif 'weight_hh' in name:
                init.orthogonal_(param)
            elif 'bias' in name:
                init.zeros_(param)
        
        init.xavier_uniform_(self.fc.weight)
        init.zeros_(self.fc.bias)
    
    def forward(self, x):
        batch_size = x.size(0)
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=x.device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=x.device)
        
        # LSTM output
        lstm_out, _ = self.lstm(x, (h0, c0))
        
        # Use only the last output
        out = lstm_out[:, -1, :]
        
        # Pass through fully connected layer
        x = self.fc(out)
        
        return x.squeeze(-1)