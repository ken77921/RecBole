# -*- coding: utf-8 -*-
# @Time   : 2020/12/31
# @Author : Zihan Lin
# @Email  : zhlin@ruc.edu.cn

r"""
MultiDAE
################################################
Reference:
    Chong Chen et al. "Efficient Neural Matrix Factorization without Sampling for Recommendation." in TOIS 2020.

Reference code:
    https://github.com/chenchongthu/ENMF
"""

import torch
import torch.nn as nn
from recbole.model.init import xavier_normal_initialization
from recbole.utils import InputType
from recbole.model.abstract_recommender import GeneralRecommender


class ENMF(GeneralRecommender):

    input_type = InputType.POINTWISE

    def __init__(self, config, dataset):
        super(ENMF, self).__init__(config, dataset)

        self.embedding_dim = config['embedding_dim']
        self.dropout_prob = config['dropout_prob']
        self.reg_weight = config['reg_weight']
        self.negative_weight = config['negative_weight']

        # get all users' history interaction information.
        # matrix is padding by the maximum number of a user's interactions
        self.history_item_matrix, _, self.history_lens = dataset.history_item_matrix()
        self.history_item_matrix = self.history_item_matrix.to(self.device)

        self.user_embedding = nn.Embedding(self.n_users, self.embedding_dim, padding_idx=0)
        self.item_embedding = nn.Embedding(self.n_items, self.embedding_dim, padding_idx=0)
        self.H_i = nn.Linear(self.embedding_dim, 1, bias=False)
        self.dropout = nn.Dropout(self.dropout_prob)

        self.apply(xavier_normal_initialization)

    def reg_loss(self):
        """calculate the reg loss for embedding layers and mlp layers

        Returns:
            torch.Tensor: reg loss

        """
        l2_reg = self.user_embedding.weight.norm(2) + self.item_embedding.weight.norm(2)
        loss_l2 = self.reg_weight * l2_reg

        return loss_l2

    def forward(self, user):
        user_embedding = self.user_embedding(user)  # shape:[B, embedding_dim]
        user_embedding = self.dropout(user_embedding)  # shape:[B, embedding_dim]

        user_inter = self.history_item_matrix[user]  # shape :[B, max_len]
        item_embedding = self.item_embedding(user_inter)  # shape: [B, max_len, embedding_dim]
        score = torch.mul(user_embedding.unsqueeze(1), item_embedding)  # shape: [B, max_len, embedding_dim]
        score = self.H_i(score)  # shape: [B,max_len,1]
        score = score.squeeze()  # shape:[B,max_len]

        return score

    def calculate_loss(self, interaction):
        user = interaction[self.USER_ID]

        pos_score = self.forward(user)

        # shape: [embedding_dim, embedding_dim]
        item_sum = torch.bmm(self.item_embedding.weight.unsqueeze(2), self.item_embedding.weight.unsqueeze(1)).sum(dim=0)

        # shape: [embedding_dim, embedding_dim]
        user_sum = torch.bmm(self.user_embedding.weight.unsqueeze(2), self.user_embedding.weight.unsqueeze(1)).sum(dim=0)

        # shape: [embedding_dim, embedding_dim]
        H_sum = torch.matmul(self.H_i.weight.t(), self.H_i.weight)

        t = torch.sum(item_sum * user_sum * H_sum)

        loss = self.negative_weight * t

        loss = loss + torch.sum((1-self.negative_weight) * torch.square(pos_score) - 2 * pos_score)

        loss = loss + self.reg_loss()

        return loss

    def predict(self, interaction):
        user = interaction[self.USER_ID]
        item = interaction[self.ITEM_ID]

        u_e = self.user_embedding(user)
        i_e = self.item_embedding(item)

        score = torch.mul(u_e, i_e)  # shape: [B,embedding_dim]
        score = self.H_i(score)  # shape: [B,1]

        return score.squeeze(1)

    def full_sort_predict(self, interaction):
        user = interaction[self.USER_ID]

        u_e = self.user_embedding(user)  # shape: [B,embedding_dim]

        all_i_e = self.item_embedding.weight  # shape: [n_item,embedding_dim]

        score = torch.mul(u_e.unsqueeze(1), all_i_e.unsqueeze(0))  # shape: [B, n_item, embedding_dim]

        score = self.H_i(score).squeeze(2)  # shape: [B, n_item]

        return score.view(-1)





