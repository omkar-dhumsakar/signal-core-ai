import random
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque

# ── Neural Network Architecture ───────────────────────────────────────

class DQNNetwork(nn.Module):
    """Deep Q-Network for SCM RL.
    
    Architecture:
    Input: [Inventory, Pipeline, Signal, SKU_Embedding]
    Output: Q-Values for each discrete action target.
    """
    def __init__(self, input_dim, output_dim, num_skus=1, embedding_dim=8):
        super(DQNNetwork, self).__init__()
        
        # SKU Embedding (useful for scaling to 40k+ SKUs)
        self.sku_embedding = nn.Embedding(num_skus, embedding_dim)
        
        # MLP Layers
        self.fc = nn.Sequential(
            nn.Linear(input_dim + embedding_dim, 128), 
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )

    def forward(self, state, sku_id):
        # state: (batch, input_dim-1) — inventory, pipeline, signal
        # sku_id: (batch,)
        sku_embed = self.sku_embedding(sku_id.long())
        x = torch.cat([state, sku_embed], dim=1)
        return self.fc(x)

# ── Replay Buffer ───────────────────────────────────────────────────

class ReplayBuffer:
    def __init__(self, capacity=10000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, sku_id, action_idx, reward, next_state, next_sku_id, done):
        self.buffer.append((state, sku_id, action_idx, reward, next_state, next_sku_id, done))

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, sku_ids, actions, rewards, next_states, next_sku_ids, dones = zip(*batch)
        return (
            torch.FloatTensor(np.array(states)),
            torch.LongTensor(np.array(sku_ids)),
            torch.LongTensor(np.array(actions)),
            torch.FloatTensor(np.array(rewards)),
            torch.FloatTensor(np.array(next_states)),
            torch.LongTensor(np.array(next_sku_ids)),
            torch.FloatTensor(np.array(dones))
        )

    def __len__(self):
        return len(self.buffer)

# ── DQN Agent ───────────────────────────────────────────────────────

class DQNAgent:
    def __init__(self, targets, num_skus=100, embedding_dim=16):
        self.targets = targets
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Hyperparameters
        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.lr = 1e-3
        self.batch_size = 64
        self.target_update_freq = 10
        
        # Modeling
        input_dim = 3 # inv, pipe, signal
        output_dim = len(targets)
        
        self.policy_net = DQNNetwork(input_dim, output_dim, num_skus, embedding_dim).to(self.device)
        self.target_net = DQNNetwork(input_dim, output_dim, num_skus, embedding_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.lr)
        self.memory = ReplayBuffer(capacity=20000)
        self.steps_done = 0

    def act(self, inv, pipe_sum, signal, sku_id=0, explore=True):
        """Select action using epsilon-greedy strategy."""
        if explore and random.random() < self.epsilon:
            return random.choice(self.targets)
            
        state = torch.FloatTensor([inv, pipe_sum, signal]).unsqueeze(0).to(self.device)
        sku = torch.LongTensor([sku_id]).to(self.device)
        
        with torch.no_grad():
            q_values = self.policy_net(state, sku)
            action_idx = q_values.argmax(dim=1).item()
            
        return self.targets[action_idx]

    def learn(self):
        """Update the Q-network weights."""
        if len(self.memory) < self.batch_size:
            return

        states, sku_ids, actions, rewards, next_states, next_sku_ids, dones = self.memory.sample(self.batch_size)
        states, sku_ids, actions, rewards, next_states, next_sku_ids, dones = \
            states.to(self.device), sku_ids.to(self.device), actions.to(self.device), \
            rewards.to(self.device), next_states.to(self.device), next_sku_ids.to(self.device), dones.to(self.device)

        # Current Q-values
        current_q = self.policy_net(states, sku_ids).gather(1, actions.unsqueeze(1))
        
        # Max next Q-values (using target network)
        with torch.no_grad():
            next_q = self.target_net(next_states, next_sku_ids).max(1)[0].unsqueeze(1)
            target_q = rewards.unsqueeze(1) + (self.gamma * next_q * (1 - dones.unsqueeze(1)))

        loss = nn.MSELoss()(current_q, target_q)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

        # Update target network
        self.steps_done += 1
        if self.steps_done % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()

    def save(self, path):
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon
        }, path)

    def load(self, path):
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['policy_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint['epsilon']
