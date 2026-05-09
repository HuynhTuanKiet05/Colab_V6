import timeit
import os
import argparse
import pandas as pd
import torch.optim as optim
import torch
import torch.nn as nn
import torch.nn.functional as fn
from data_preprocess import *
from model.RLGHGT import RLGHGT
from metric import *

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--k_fold', type=int, default=10, help='k-fold cross validation')
    parser.add_argument('--epochs', type=int, default=1000, help='number of epochs to train')
    parser.add_argument('--lr', type=float, default=1e-3, help='learning rate')
    parser.add_argument('--weight_decay', type=float, default=1e-4, help='weight_decay')
    parser.add_argument('--random_seed', type=int, default=1234, help='random seed')
    parser.add_argument('--neighbor', type=int, default=20, help='neighbor')
    parser.add_argument('--negative_rate', type=float, default=1.0, help='negative_rate')
    parser.add_argument('--dataset', default='C-dataset', help='dataset')
    parser.add_argument('--dropout', default=0.2, type=float, help='dropout')
    parser.add_argument('--gt_layer', default=2, type=int, help='graph transformer layer')
    parser.add_argument('--gt_head', default=2, type=int, help='graph transformer head')
    parser.add_argument('--gt_out_dim', default=200, type=int, help='graph transformer output dimension')
    parser.add_argument('--hgt_layer', default=3, type=int, help='heterogeneous graph transformer layer')
    parser.add_argument('--hgt_head', default=8, type=int, help='heterogeneous graph transformer head')
    parser.add_argument('--hgt_in_dim', default=128, type=int, help='heterogeneous graph transformer input dimension')
    parser.add_argument('--hgt_head_dim', default=25, type=int, help='heterogeneous graph transformer head dimension')
    parser.add_argument('--tr_layer', default=2, type=int, help='transformer layer')
    parser.add_argument('--tr_head', default=4, type=int, help='transformer head')
    parser.add_argument('--patience', default=None, type=int, help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.patience is not None:
        print('Note: --patience is deprecated and ignored; training now runs for the full epoch count.')
    args.data_dir = 'data/' + args.dataset + '/'
    args.result_dir = 'Result/' + args.dataset + '/RLGHGT_v2/'
    os.makedirs(args.result_dir, exist_ok=True)

    data = get_data(args)
    args.drug_number = data['drug_number']
    args.disease_number = data['disease_number']
    args.protein_number = data['protein_number']

    data = data_processing(data, args)
    data = k_fold(data, args)

    drdr_graph, didi_graph, data = dgl_similarity_graph(data, args)
    drdr_graph = drdr_graph.to(device)
    didi_graph = didi_graph.to(device)

    drug_feature = torch.FloatTensor(data['drugfeature']).to(device)
    disease_feature = torch.FloatTensor(data['diseasefeature']).to(device)
    protein_feature = torch.FloatTensor(data['proteinfeature']).to(device)

    Metric_Header = ('Epoch\t\tTime\t\tAUC\t\tAUPR\t\tAccuracy\t\tPrecision\t\tRecall\t\tF1-score\t\tMcc')
    AUCs, AUPRs, Accs, Precs, Recs, F1s, MCCs, Epochs = [], [], [], [], [], [], [], []

    print(f'Training RLGHGT v2 on Dataset: {args.dataset}')

    for i in range(args.k_fold):
        print(f'\n--- Fold: {i} ---')
        print(Metric_Header)

        model = RLGHGT(args).to(device)
        optimizer = optim.Adam(model.parameters(), weight_decay=args.weight_decay, lr=args.lr)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

        best_auc = 0
        best_metrics = None
        
        X_train = torch.LongTensor(data['X_train'][i]).to(device)
        Y_train = torch.LongTensor(data['Y_train'][i]).to(device)
        X_test = torch.LongTensor(data['X_test'][i]).to(device)
        Y_test = data['Y_test'][i].flatten()

        # Tính toán pos_weight cho Weighted Cross Entropy
        n_pos = torch.sum(Y_train).item()
        n_neg = Y_train.numel() - n_pos
        pos_weight = torch.tensor([n_neg / n_pos]).to(device)
        criterion = nn.CrossEntropyLoss(weight=torch.tensor([1.0, n_neg/n_pos]).to(device))

        drdipr_graph, data = dgl_heterograph(data, data['X_train'][i], args)
        drdipr_graph = drdipr_graph.to(device)

        start = timeit.default_timer()

        for epoch in range(args.epochs):
            model.train()
            _, train_score = model(drdr_graph, didi_graph, drdipr_graph, drug_feature, disease_feature, protein_feature, X_train)
            train_loss = criterion(train_score, torch.flatten(Y_train))
            
            optimizer.zero_grad()
            train_loss.backward()
            optimizer.step()
            scheduler.step()

            if (epoch + 1) % 10 == 0 or epoch == 0:
                model.eval()
                with torch.no_grad():
                    _, test_score = model(drdr_graph, didi_graph, drdipr_graph, drug_feature, disease_feature, protein_feature, X_test)
                
                test_prob = fn.softmax(test_score, dim=-1)[:, 1].cpu().numpy()
                test_pred = torch.argmax(test_score, dim=-1).cpu().numpy()

                AUC, AUPR, accuracy, precision, recall, f1, mcc = get_metric(Y_test, test_pred, test_prob)

                if AUC > best_auc:
                    best_auc = AUC
                    best_metrics = (AUC, AUPR, accuracy, precision, recall, f1, mcc, epoch + 1)
                    torch.save(model.state_dict(), os.path.join(args.result_dir, f'best_model_fold_{i}.pth'))
                
                time_now = timeit.default_timer() - start
                print(f'{epoch+1}\t\t{time_now:.2f}\t\t{AUC:.5f}\t\t{AUPR:.5f}\t\t{accuracy:.5f}\t\t{precision:.5f}\t\t{recall:.5f}\t\t{f1:.5f}\t\t{mcc:.5f}')

        if best_metrics:
            AUCs.append(best_metrics[0]); AUPRs.append(best_metrics[1]); Accs.append(best_metrics[2])
            Precs.append(best_metrics[3]); Recs.append(best_metrics[4]); F1s.append(best_metrics[5])
            MCCs.append(best_metrics[6]); Epochs.append(best_metrics[7])
            print(f'Fold {i} Best AUC: {best_metrics[0]:.5f} (Epoch {best_metrics[7]})')
        
        del model, optimizer, scheduler, drdipr_graph
        torch.cuda.empty_cache()

    # Final Results Processing
    results_df = pd.DataFrame({
        'Fold': [f'Fold {i}' for i in range(len(AUCs))],
        'Best_Epoch': Epochs,
        'AUC': AUCs, 'AUPR': AUPRs, 'Accuracy': Accs, 
        'Precision': Precs, 'Recall': Recs, 'F1-score': F1s, 'Mcc': MCCs
    })
    
    metrics_only = results_df.drop(columns=['Fold', 'Best_Epoch'])
    summary_df = pd.DataFrame([['Mean', ''] + metrics_only.mean().tolist(), ['Std', ''] + metrics_only.std().tolist()], columns=results_df.columns)
    final_df = pd.concat([results_df, summary_df], ignore_index=True)
    
    print('\n' + '='*30 + '\nFINAL RESULTS SUMMARY\n' + '='*30)
    print(final_df.iloc[-2:])
    
    csv_path = os.path.join(args.result_dir, '10_fold_results_RLGHGT_v2.csv')
    final_df.to_csv(csv_path, index=False)
    print(f'\nKết quả v2 đã được lưu tại: {csv_path}')
