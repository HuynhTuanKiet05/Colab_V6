<?php
require_once __DIR__ . '/../app/bootstrap.php';

// Path definitions
$datasets = ['B-dataset', 'C-dataset', 'F-dataset'];
$improvedBasePath = __DIR__ . '/../Result/improved/';
$baselineBasePath = __DIR__ . '/../AMDGT_original/Result/'; 

function parseCSV($filePath) {
    if (!file_exists($filePath)) {
        return null;
    }
    $data = [];
    if (($handle = fopen($filePath, "r")) !== FALSE) {
        $header = fgetcsv($handle, 1000, ",");
        $idx_auc = array_search('AUC', $header);
        $idx_aupr = array_search('AUPR', $header);
        $idx_f1 = array_search('F1-score', $header);
        if ($idx_f1 === false) $idx_f1 = array_search('F1', $header);
        
        while (($row = fgetcsv($handle, 1000, ",")) !== FALSE) {
            if (empty($row[0])) continue;
            
            $fold = $row[0];
            $auc = isset($row[$idx_auc]) && is_numeric($row[$idx_auc]) ? round($row[$idx_auc] * 100, 2) : 0;
            $aupr = isset($row[$idx_aupr]) && is_numeric($row[$idx_aupr]) ? round($row[$idx_aupr] * 100, 2) : 0;
            $f1 = isset($row[$idx_f1]) && is_numeric($row[$idx_f1]) ? round($row[$idx_f1] * 100, 2) : 0;
            
            $data[strtolower($fold)] = [
                'auc' => $auc,
                'aupr' => $aupr,
                'f1' => $f1
            ];
        }
        fclose($handle);
    }
    return $data;
}

// Hàm sinh dữ liệu mock cho Baseline trong trường hợp chưa có file CSV
function generateMockBaseline() {
    $data = [];
    for ($i = 0; $i < 10; $i++) {
        $data["fold $i"] = [
            'auc' => round(94.0 + mt_rand(0, 150)/100, 2),
            'aupr' => round(93.0 + mt_rand(0, 200)/100, 2),
            'f1' => round(88.0 + mt_rand(0, 200)/100, 2)
        ];
    }
    $data["mean"] = [
        'auc' => 95.11,
        'aupr' => 94.99,
        'f1' => 88.98
    ];
    return $data;
}

$results = [];

foreach ($datasets as $dataset) {
    // 1. Tìm file CSV Improved
    $improvedFile = null;
    $dir = $improvedBasePath . $dataset . '/';
    if (is_dir($dir)) {
        $files = scandir($dir);
        foreach ($files as $f) {
            if (strpos($f, '10_fold_results') !== false && strpos($f, '.csv') !== false) {
                $improvedFile = $dir . $f;
                break;
            }
        }
    }
    $improvedData = $improvedFile ? parseCSV($improvedFile) : null;
    
    // 2. Tìm file CSV Baseline (nếu user tạo sau này trong Result/baseline)
    $baselineFile = __DIR__ . '/../Result/baseline/' . $dataset . '/10_fold_results.csv';
    $baselineData = parseCSV($baselineFile);
    
    // Sử dụng dữ liệu giả lập cho Baseline nếu không tìm thấy file để test UI
    $isBaselineMock = false;
    if (!$baselineData) {
        $baselineData = generateMockBaseline();
        $isBaselineMock = true;
    }
    
    $results[$dataset] = [
        'improved' => $improvedData,
        'baseline' => $baselineData,
        'isBaselineMock' => $isBaselineMock
    ];
}

$activeTab = isset($_GET['dataset']) && in_array($_GET['dataset'], $datasets) ? $_GET['dataset'] : 'F-dataset';
$currentData = $results[$activeTab];

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Comparison Results</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: #111526;
            --border-color: #1f2940;
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --green-accent: #22c55e;
            --yellow-accent: #eab308;
            --yellow-bg: rgba(234, 179, 8, 0.1);
            --header-bg: #1c233a;
            --button-bg: #1e293b;
            --button-hover: #334155;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }

        /* TABS */
        .tabs {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
        }

        .tab {
            padding: 10px 25px;
            background: var(--button-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-muted);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.95rem;
            transition: all 0.3s ease;
        }

        .tab:hover {
            background: var(--button-hover);
            color: white;
        }

        .tab.active {
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border-color: #3b82f6;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
        }

        .results-container {
            width: 100%;
            max-width: 900px;
            background: linear-gradient(145deg, var(--card-bg), #0d1222);
            border-radius: 16px;
            border: 1px solid var(--border-color);
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            position: relative;
        }

        /* Subtle glow on top left */
        .results-container::before {
            content: '';
            position: absolute;
            top: -40px;
            left: -40px;
            width: 120px;
            height: 120px;
            background: rgba(59, 130, 246, 0.15);
            filter: blur(40px);
            border-radius: 50%;
            z-index: 0;
            pointer-events: none;
        }

        .title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
            color: white;
            position: relative;
            z-index: 1;
        }

        .alert-mock {
            font-size: 0.8rem;
            color: var(--yellow-accent);
            background: var(--yellow-bg);
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(234, 179, 8, 0.2);
        }

        .table-wrapper {
            border: 1px solid var(--border-color);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
            z-index: 1;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: center;
        }

        th {
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .main-header {
            background: var(--header-bg);
        }

        .main-header th {
            font-size: 0.75rem;
            padding: 15px 10px;
        }

        .sub-header th {
            font-size: 0.75rem;
            padding: 12px 10px;
            border-bottom: 1px solid var(--border-color);
            background: rgba(28, 35, 58, 0.5);
        }

        td {
            padding: 14px 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            font-weight: 500;
        }

        tbody tr:hover {
            background-color: rgba(255, 255, 255, 0.02);
        }

        .col-fold {
            text-align: left;
            padding-left: 30px !important;
            color: white;
            font-weight: 600;
        }

        .col-baseline {
            color: #d1d5db;
        }

        .col-improved {
            color: var(--green-accent);
        }

        /* Mean row styling */
        .row-mean td {
            color: var(--yellow-accent);
            font-weight: 700;
            background-color: var(--yellow-bg);
            border-bottom: none;
        }

        .footer {
            margin-top: 30px;
            text-align: center;
            font-size: 0.75rem;
            color: var(--text-muted);
            position: relative;
            z-index: 1;
        }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: var(--text-muted);
        }

        /* Vertical borders to match image */
        .main-header th:nth-child(2) {
            border-right: 1px solid var(--border-color);
        }
        .sub-header th:nth-child(4) {
            border-right: 1px solid rgba(255,255,255,0.05);
        }
        td:nth-child(4) {
            border-right: 1px solid rgba(255,255,255,0.05);
        }
    </style>
</head>
<body>

    <div class="tabs">
        <?php foreach ($datasets as $ds): ?>
            <a href="?dataset=<?= $ds ?>" class="tab <?= $activeTab === $ds ? 'active' : '' ?>">
                <?= str_replace('-dataset', ' Dataset', $ds) ?>
            </a>
        <?php endforeach; ?>
    </div>

    <div class="results-container">
        <div class="title">
            <i class="fa-solid fa-layer-group"></i>
            Fold-by-Fold Results
        </div>

        <?php if ($currentData['isBaselineMock']): ?>
            <div class="alert-mock">
                <i class="fa-solid fa-circle-info"></i>
                Dữ liệu Baseline đang là mock demo. Bạn có thể tạo folder <code>Result/baseline/<?= $activeTab ?>/10_fold_results.csv</code> để hiển thị dữ liệu thật.
            </div>
        <?php endif; ?>

        <?php if (empty($currentData['improved'])): ?>
            <div class="no-data">
                <i class="fa-solid fa-triangle-exclamation fa-3x mb-3" style="color: var(--yellow-accent); margin-bottom: 15px; display: block;"></i>
                <p>Chưa tìm thấy dữ liệu CSV của mô hình Improved cho <strong><?= htmlspecialchars($activeTab) ?></strong>.</p>
                <p style="font-size: 0.85rem; margin-top: 10px;">Đường dẫn tìm kiếm: <code>Result/improved/<?= htmlspecialchars($activeTab) ?>/</code></p>
            </div>
        <?php else: ?>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr class="main-header">
                            <th style="width: 20%;">FOLD</th>
                            <th colspan="3">BASELINE</th>
                            <th colspan="3">IMPROVED</th>
                        </tr>
                        <tr class="sub-header">
                            <th class="col-fold"></th>
                            <th>AUC</th>
                            <th>AUPR</th>
                            <th>F1</th>
                            <th>AUC</th>
                            <th>AUPR</th>
                            <th>F1</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php 
                        for ($i = 0; $i < 10; $i++): 
                            $foldKey = "fold $i";
                            $imp = isset($currentData['improved'][$foldKey]) ? $currentData['improved'][$foldKey] : ['auc'=>'-', 'aupr'=>'-', 'f1'=>'-'];
                            $base = isset($currentData['baseline'][$foldKey]) ? $currentData['baseline'][$foldKey] : ['auc'=>'-', 'aupr'=>'-', 'f1'=>'-'];
                        ?>
                        <tr>
                            <td class="col-fold">Fold <?= $i ?></td>
                            <td class="col-baseline"><?= $base['auc'] ?></td>
                            <td class="col-baseline"><?= $base['aupr'] ?></td>
                            <td class="col-baseline"><?= $base['f1'] ?></td>
                            <td class="col-improved"><?= $imp['auc'] ?></td>
                            <td class="col-improved"><?= $imp['aupr'] ?></td>
                            <td class="col-improved"><?= $imp['f1'] ?></td>
                        </tr>
                        <?php endfor; ?>

                        <?php 
                            $impMean = isset($currentData['improved']['mean']) ? $currentData['improved']['mean'] : ['auc'=>'-', 'aupr'=>'-', 'f1'=>'-'];
                            $baseMean = isset($currentData['baseline']['mean']) ? $currentData['baseline']['mean'] : ['auc'=>'-', 'aupr'=>'-', 'f1'=>'-'];
                        ?>
                        <tr class="row-mean">
                            <td class="col-fold">MEAN</td>
                            <td><?= $baseMean['auc'] ?></td>
                            <td><?= $baseMean['aupr'] ?></td>
                            <td><?= $baseMean['f1'] ?></td>
                            <td><?= $impMean['auc'] ?></td>
                            <td><?= $impMean['aupr'] ?></td>
                            <td><?= $impMean['f1'] ?></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        <?php endif; ?>

        <div class="footer">
            © 2026 AMDGT - Attention-aware Multi-modal Dual Graph Transformer
        </div>
    </div>

</body>
</html>
