#!/usr/bin/env node
/**
 * Financial Documents Processing - PowerPoint Presentation Generator
 * Creates a professional 8-slide presentation highlighting unique features and differentiators
 */

const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

// Create presentation
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_16x9';
pptx.title = 'Financial Documents Processing - Router Pattern Architecture';
pptx.author = 'AWS Solutions';
pptx.subject = 'Cost-Optimized Intelligent Document Processing';

// Color palette (AWS-inspired, no # prefix for pptxgenjs)
const colors = {
    primary: 'FF9900',      // AWS Orange
    secondary: '232F3E',    // AWS Navy
    accent: '1A73E8',       // Blue
    success: '22C55E',      // Green
    warning: 'F59E0B',      // Amber
    danger: 'EF4444',       // Red
    light: 'F8FAFC',        // Light gray
    dark: '1E293B',         // Dark slate
    purple: '8B5CF6',       // Purple
    teal: '14B8A6',         // Teal
};

// Common styles
const titleStyle = { fontSize: 36, bold: true, color: colors.dark, fontFace: 'Arial' };
const subtitleStyle = { fontSize: 20, color: colors.secondary, fontFace: 'Arial' };
const bodyStyle = { fontSize: 16, color: colors.dark, fontFace: 'Arial' };
const bulletStyle = { fontSize: 14, color: colors.dark, fontFace: 'Arial', bullet: { type: 'bullet' } };

// ============================================================================
// SLIDE 1: Title Slide
// ============================================================================
let slide1 = pptx.addSlide();
slide1.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: '100%', fill: { color: colors.light } });
slide1.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 0.15, fill: { color: colors.primary } });
slide1.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 5.475, w: '100%', h: 0.15, fill: { color: colors.primary } });

slide1.addText('Financial Documents Processing', { x: 0.5, y: 1.8, w: 9, h: 0.8, ...titleStyle, fontSize: 44 });
slide1.addText('Router Pattern Architecture', { x: 0.5, y: 2.7, w: 9, h: 0.5, ...subtitleStyle, fontSize: 28, color: colors.primary, bold: true });
slide1.addText('Cost-Optimized Intelligent Document Processing for Financial Services', { x: 0.5, y: 3.4, w: 9, h: 0.4, ...subtitleStyle });

slide1.addText([
    { text: '92.5% Cost Reduction', options: { bold: true, color: colors.success } },
    { text: '  |  ', options: { color: colors.dark } },
    { text: 'Serverless AWS Architecture', options: { color: colors.dark } },
    { text: '  |  ', options: { color: colors.dark } },
    { text: 'AI-Powered Classification', options: { color: colors.dark } },
], { x: 0.5, y: 4.5, w: 9, h: 0.4, fontSize: 14, fontFace: 'Arial' });

// ============================================================================
// SLIDE 2: The Problem
// ============================================================================
let slide2 = pptx.addSlide();
slide2.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.secondary } });
slide2.addText('The Problem: Traditional Document Processing', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Problem boxes
const problems = [
    { icon: '💸', title: '$4.50+/doc', desc: 'Brute force OCR on every page\nof multi-hundred page documents' },
    { icon: '⏱️', title: 'Slow Processing', desc: 'Sequential page-by-page\nextraction wastes time' },
    { icon: '🎯', title: 'Low Precision', desc: 'Generic extraction misses\nfinancial document nuances' },
    { icon: '📋', title: 'No Audit Trail', desc: 'Difficult to trace which\npage data came from' },
];

problems.forEach((p, i) => {
    const x = 0.4 + (i * 2.4);
    slide2.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x, y: 1.6, w: 2.2, h: 2.8, fill: { color: 'FFFFFF' }, line: { color: colors.danger, pt: 2 }, rectRadius: 0.1 });
    slide2.addText(p.icon, { x, y: 1.8, w: 2.2, h: 0.5, fontSize: 36, align: 'center' });
    slide2.addText(p.title, { x, y: 2.4, w: 2.2, h: 0.4, fontSize: 16, bold: true, color: colors.danger, align: 'center', fontFace: 'Arial' });
    slide2.addText(p.desc, { x: x + 0.1, y: 3.0, w: 2, h: 1.2, fontSize: 11, color: colors.dark, align: 'center', fontFace: 'Arial' });
});

slide2.addText('Result: Processing 1,000 documents/month costs $4,500+ with limited accuracy',
    { x: 0.5, y: 4.8, w: 9, h: 0.4, fontSize: 16, color: colors.danger, bold: true, fontFace: 'Arial', align: 'center' });

// ============================================================================
// SLIDE 3: The Solution - Router Pattern
// ============================================================================
let slide3 = pptx.addSlide();
slide3.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.primary } });
slide3.addText('The Solution: Router Pattern', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Three-stage pipeline
const stages = [
    { num: '1', title: 'ROUTER', subtitle: 'Classification', desc: 'Claude 3 Haiku analyzes\nall pages, identifies key\ndocuments & page numbers', cost: '~$0.006', color: colors.accent },
    { num: '2', title: 'EXTRACTOR', subtitle: 'Targeted Pages', desc: 'Textract processes ONLY\nidentified pages with\nTables + Queries', cost: '~$0.30', color: colors.teal },
    { num: '3', title: 'NORMALIZER', subtitle: 'Refinement', desc: 'Claude 3.5 Haiku normalizes\ndata, cross-validates,\nproduces schema JSON', cost: '~$0.03', color: colors.purple },
];

stages.forEach((s, i) => {
    const x = 0.5 + (i * 3.2);
    slide3.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 3, h: 3.2, fill: { color: 'FFFFFF' }, line: { color: s.color, pt: 3 }, rectRadius: 0.15 });
    slide3.addShape(pptx.shapes.OVAL, { x: x + 1.1, y: 1.7, w: 0.8, h: 0.8, fill: { color: s.color } });
    slide3.addText(s.num, { x: x + 1.1, y: 1.8, w: 0.8, h: 0.6, fontSize: 24, bold: true, color: 'FFFFFF', align: 'center', fontFace: 'Arial' });
    slide3.addText(s.title, { x, y: 2.7, w: 3, h: 0.4, fontSize: 18, bold: true, color: s.color, align: 'center', fontFace: 'Arial' });
    slide3.addText(s.subtitle, { x, y: 3.1, w: 3, h: 0.3, fontSize: 12, color: colors.dark, align: 'center', fontFace: 'Arial' });
    slide3.addText(s.desc, { x: x + 0.1, y: 3.5, w: 2.8, h: 0.9, fontSize: 11, color: colors.dark, align: 'center', fontFace: 'Arial' });
    slide3.addText(s.cost, { x, y: 4.3, w: 3, h: 0.3, fontSize: 14, bold: true, color: colors.success, align: 'center', fontFace: 'Arial' });

    // Arrow between stages
    if (i < 2) {
        slide3.addShape(pptx.shapes.RIGHT_ARROW, { x: x + 3.1, y: 2.9, w: 0.4, h: 0.4, fill: { color: colors.primary } });
    }
});

slide3.addText('Total: ~$0.34/document (vs $4.55 brute force)',
    { x: 0.5, y: 4.9, w: 9, h: 0.4, fontSize: 18, color: colors.success, bold: true, fontFace: 'Arial', align: 'center' });

// ============================================================================
// SLIDE 4: Architecture Overview
// ============================================================================
let slide4 = pptx.addSlide();
slide4.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.secondary } });
slide4.addText('Architecture Overview', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Add the architecture diagram
const diagramPath = path.join(__dirname, '../docs/aws-architecture-horizontal.png');
if (fs.existsSync(diagramPath)) {
    slide4.addImage({ path: diagramPath, x: 0.3, y: 1.4, w: 9.4, h: 4.0 });
} else {
    slide4.addText('Architecture diagram: docs/aws-architecture-horizontal.png',
        { x: 1, y: 2.5, w: 8, h: 1, fontSize: 16, color: colors.dark, align: 'center' });
}

// ============================================================================
// SLIDE 5: Cost Comparison
// ============================================================================
let slide5 = pptx.addSlide();
slide5.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.success } });
slide5.addText('Cost Comparison: 92.5% Savings', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Cost comparison table
slide5.addTable([
    [
        { text: 'Approach', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true } },
        { text: 'Cost/Doc', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true } },
        { text: '1,000 Docs/Month', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true } },
        { text: '10,000 Docs/Month', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true } },
    ],
    [
        { text: 'Brute Force OCR', options: { fill: { color: 'FEE2E2' } } },
        { text: '$4.55', options: { fill: { color: 'FEE2E2' }, color: colors.danger, bold: true } },
        { text: '$4,550', options: { fill: { color: 'FEE2E2' } } },
        { text: '$45,500', options: { fill: { color: 'FEE2E2' } } },
    ],
    [
        { text: 'Router Pattern', options: { fill: { color: 'DCFCE7' } } },
        { text: '$0.34', options: { fill: { color: 'DCFCE7' }, color: colors.success, bold: true } },
        { text: '$340', options: { fill: { color: 'DCFCE7' } } },
        { text: '$3,400', options: { fill: { color: 'DCFCE7' } } },
    ],
    [
        { text: 'Monthly Savings', options: { fill: { color: colors.success }, color: 'FFFFFF', bold: true } },
        { text: '$4.21', options: { fill: { color: colors.success }, color: 'FFFFFF', bold: true } },
        { text: '$4,210', options: { fill: { color: colors.success }, color: 'FFFFFF', bold: true } },
        { text: '$42,100', options: { fill: { color: colors.success }, color: 'FFFFFF', bold: true } },
    ],
], {
    x: 0.5, y: 1.5, w: 9, h: 2.2,
    colW: [2.5, 1.8, 2.35, 2.35],
    border: { pt: 1, color: 'DDDDDD' },
    align: 'center',
    valign: 'middle',
    fontSize: 14,
    fontFace: 'Arial',
});

// Cost breakdown chart
slide5.addText('Per-Document Cost Breakdown (300-page Credit Agreement)',
    { x: 0.5, y: 3.9, w: 9, h: 0.3, fontSize: 14, bold: true, color: colors.dark, fontFace: 'Arial' });

slide5.addChart(pptx.charts.BAR, [{
    name: 'Cost',
    labels: ['Router (Haiku)', 'Extractor (Textract)', 'Normalizer (Haiku)'],
    values: [0.006, 0.30, 0.03]
}], {
    x: 0.5, y: 4.2, w: 4.5, h: 1.3,
    barDir: 'bar',
    showValue: true,
    dataLabelPosition: 'outEnd',
    dataLabelFontSize: 10,
    chartColors: [colors.accent],
    showCatAxisTitle: false,
    showValAxisTitle: true,
    valAxisTitle: 'Cost ($)',
    valAxisMaxVal: 0.35,
});

// Pie chart for cost distribution
slide5.addChart(pptx.charts.PIE, [{
    name: 'Cost Distribution',
    labels: ['Textract (89%)', 'Normalizer (9%)', 'Router (2%)'],
    values: [0.30, 0.03, 0.006]
}], {
    x: 5.3, y: 4.1, w: 4.2, h: 1.5,
    showPercent: true,
    showLegend: true,
    legendPos: 'r',
    chartColors: [colors.teal, colors.purple, colors.accent],
});

// ============================================================================
// SLIDE 6: Why Router Pattern? (vs Alternatives)
// ============================================================================
let slide6 = pptx.addSlide();
slide6.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.danger } });
slide6.addText('Why Router Pattern? vs Alternatives', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 28, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Comparison table
slide6.addTable([
    [
        { text: 'Approach', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true, fontSize: 11 } },
        { text: 'Cost/Doc', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true, fontSize: 11 } },
        { text: '10K Docs/Mo', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true, fontSize: 11 } },
        { text: 'Key Limitation', options: { fill: { color: colors.secondary }, color: 'FFFFFF', bold: true, fontSize: 11 } },
    ],
    [
        { text: 'Claude Opus 4.5\n(Tool Calling)', options: { fill: { color: 'FEE2E2' }, fontSize: 10 } },
        { text: '$15-25', options: { fill: { color: 'FEE2E2' }, color: colors.danger, bold: true, fontSize: 10 } },
        { text: '$150K+', options: { fill: { color: 'FEE2E2' }, fontSize: 10 } },
        { text: 'Context limits; cost prohibitive', options: { fill: { color: 'FEE2E2' }, fontSize: 10 } },
    ],
    [
        { text: 'Bedrock Data\nAutomation (BDA)', options: { fill: { color: 'FEF3C7' }, fontSize: 10 } },
        { text: '$2-5', options: { fill: { color: 'FEF3C7' }, color: colors.warning, bold: true, fontSize: 10 } },
        { text: '$25K+', options: { fill: { color: 'FEF3C7' }, fontSize: 10 } },
        { text: 'No page selection; black-box', options: { fill: { color: 'FEF3C7' }, fontSize: 10 } },
    ],
    [
        { text: 'Full Textract OCR\n(Brute Force)', options: { fill: { color: 'FEF3C7' }, fontSize: 10 } },
        { text: '$4.55', options: { fill: { color: 'FEF3C7' }, color: colors.warning, bold: true, fontSize: 10 } },
        { text: '$45K', options: { fill: { color: 'FEF3C7' }, fontSize: 10 } },
        { text: 'No intelligence; processes all pages', options: { fill: { color: 'FEF3C7' }, fontSize: 10 } },
    ],
    [
        { text: 'Router Pattern', options: { fill: { color: 'DCFCE7' }, bold: true, fontSize: 10 } },
        { text: '$0.34', options: { fill: { color: 'DCFCE7' }, color: colors.success, bold: true, fontSize: 10 } },
        { text: '$3,400', options: { fill: { color: 'DCFCE7' }, bold: true, fontSize: 10 } },
        { text: 'Surgical precision; 92.5% savings', options: { fill: { color: 'DCFCE7' }, color: colors.success, bold: true, fontSize: 10 } },
    ],
], {
    x: 0.3, y: 1.4, w: 9.4, h: 2.0,
    colW: [2.0, 1.3, 1.5, 4.6],
    border: { pt: 1, color: 'DDDDDD' },
    align: 'center',
    valign: 'middle',
    fontFace: 'Arial',
});

// Core insight
slide6.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: 0.3, y: 3.6, w: 9.4, h: 0.7, fill: { color: colors.accent }, rectRadius: 0.1 });
slide6.addText('"Use a cheap model to figure out WHERE to look, then use specialized tools to extract WHAT you need."',
    { x: 0.4, y: 3.7, w: 9.2, h: 0.5, fontSize: 13, italic: true, color: 'FFFFFF', align: 'center', fontFace: 'Arial' });

// Why boxes
const whyBoxes = [
    { title: 'Classification is CHEAP', desc: 'Claude Haiku excels at\ndocument structure', cost: '$0.006', color: colors.accent },
    { title: 'OCR is SPECIALIZED', desc: 'Textract beats LLM\nvision for tables', cost: '$0.02/pg', color: colors.teal },
    { title: 'Normalization needs SOME intelligence', desc: 'But not $75/M\noutput token intelligence', cost: '$0.03', color: colors.purple },
];

whyBoxes.forEach((b, i) => {
    const x = 0.4 + (i * 3.2);
    slide6.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x, y: 4.5, w: 3, h: 1.0, fill: { color: 'FFFFFF' }, line: { color: b.color, pt: 2 }, rectRadius: 0.08 });
    slide6.addText(b.title, { x, y: 4.55, w: 3, h: 0.3, fontSize: 11, bold: true, color: b.color, align: 'center', fontFace: 'Arial' });
    slide6.addText(b.desc, { x, y: 4.85, w: 3, h: 0.4, fontSize: 9, color: colors.dark, align: 'center', fontFace: 'Arial' });
    slide6.addText(b.cost, { x, y: 5.25, w: 3, h: 0.2, fontSize: 10, bold: true, color: colors.success, align: 'center', fontFace: 'Arial' });
});

// ============================================================================
// SLIDE 7: Key Differentiators
// ============================================================================
let slide7 = pptx.addSlide();
slide7.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.purple } });
slide7.addText('Key Differentiators', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

const differentiators = [
    { title: 'Intelligent Classification', desc: 'AI identifies document types & relevant pages before expensive OCR', icon: '🧠' },
    { title: 'Targeted Extraction', desc: 'Process only pages that matter - not the entire document', icon: '🎯' },
    { title: 'Content Deduplication', desc: 'SHA-256 hashing prevents reprocessing identical documents', icon: '🔒' },
    { title: 'Complete Audit Trail', desc: 'Track exactly which page each data point originated from', icon: '📊' },
    { title: 'Review Workflow', desc: 'Human-in-the-loop: Approve, Reject, or Correct extracted data', icon: '✅' },
    { title: 'Serverless & Scalable', desc: 'Zero infrastructure management, auto-scales to any volume', icon: '☁️' },
];

differentiators.forEach((d, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.4 + (col * 4.8);
    const y = 1.4 + (row * 1.3);

    slide7.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.6, h: 1.15, fill: { color: 'FFFFFF' }, line: { color: colors.purple, pt: 1 }, rectRadius: 0.08 });
    slide7.addText(d.icon, { x: x + 0.1, y: y + 0.25, w: 0.6, h: 0.6, fontSize: 24 });
    slide7.addText(d.title, { x: x + 0.8, y: y + 0.15, w: 3.6, h: 0.35, fontSize: 14, bold: true, color: colors.dark, fontFace: 'Arial' });
    slide7.addText(d.desc, { x: x + 0.8, y: y + 0.55, w: 3.6, h: 0.5, fontSize: 11, color: colors.secondary, fontFace: 'Arial' });
});

// ============================================================================
// SLIDE 8: Supported Document Types
// ============================================================================
let slide8 = pptx.addSlide();
slide8.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: 1.2, fill: { color: colors.teal } });
slide8.addText('Supported Document Types', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Loan Packages
slide8.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: 0.4, y: 1.4, w: 4.6, h: 3.8, fill: { color: 'F0FDFA' }, line: { color: colors.teal, pt: 2 }, rectRadius: 0.1 });
slide8.addText('📄 Loan Packages', { x: 0.5, y: 1.55, w: 4.4, h: 0.4, fontSize: 18, bold: true, color: colors.teal, fontFace: 'Arial' });

const loanDocs = [
    'Promissory Note - Interest rate, principal, borrower names, maturity date',
    'Closing Disclosure - Loan amount, fees, cash to close',
    'Form 1003 - Borrower info, property address, employment',
];
slide8.addText(loanDocs.map(d => ({ text: d, options: { bullet: { type: 'bullet' }, paraSpaceBefore: 8 } })),
    { x: 0.6, y: 2.1, w: 4.2, h: 2.8, fontSize: 12, color: colors.dark, fontFace: 'Arial' });

// Credit Agreements
slide8.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: 5, y: 1.4, w: 4.6, h: 3.8, fill: { color: 'FAF5FF' }, line: { color: colors.purple, pt: 2 }, rectRadius: 0.1 });
slide8.addText('📋 Credit Agreements', { x: 5.1, y: 1.55, w: 4.4, h: 0.4, fontSize: 18, bold: true, color: colors.purple, fontFace: 'Arial' });

const creditDocs = [
    'Agreement Info - Type, dates, amendment number',
    'Parties - Borrower, agent, arrangers, guarantors',
    'Facility Terms - Revolving credit, LC commitments',
    'Pricing Grid - SOFR spreads, ABR spreads, tiers',
    'Lender Commitments - Per-lender allocations',
    'Covenants - Financial ratios, requirements',
];
slide8.addText(creditDocs.map(d => ({ text: d, options: { bullet: { type: 'bullet' }, paraSpaceBefore: 6 } })),
    { x: 5.2, y: 2.1, w: 4.2, h: 2.8, fontSize: 11, color: colors.dark, fontFace: 'Arial' });

// ============================================================================
// SLIDE 9: Technology Stack & Call to Action
// ============================================================================
let slide9 = pptx.addSlide();
slide9.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: '100%', h: '100%', fill: { color: colors.secondary } });

slide9.addText('Built on AWS', { x: 0.5, y: 0.4, w: 9, h: 0.5, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Arial' });

// Tech stack grid
const techStack = [
    { service: 'CloudFront + S3', purpose: 'React Dashboard' },
    { service: 'API Gateway + Lambda', purpose: 'REST API' },
    { service: 'Step Functions', purpose: 'Orchestration' },
    { service: 'Bedrock (Claude Haiku)', purpose: 'AI Classification' },
    { service: 'Textract', purpose: 'OCR Extraction' },
    { service: 'DynamoDB + S3', purpose: 'Data Storage' },
];

techStack.forEach((t, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.5 + (col * 3.15);
    const y = 1.2 + (row * 1.1);

    slide9.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x, y, w: 3, h: 0.95, fill: { color: colors.primary }, rectRadius: 0.08 });
    slide9.addText(t.service, { x, y: y + 0.15, w: 3, h: 0.35, fontSize: 13, bold: true, color: 'FFFFFF', align: 'center', fontFace: 'Arial' });
    slide9.addText(t.purpose, { x, y: y + 0.5, w: 3, h: 0.3, fontSize: 11, color: 'FFFFFF', align: 'center', fontFace: 'Arial' });
});

// Call to action
slide9.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: 1.5, y: 3.6, w: 7, h: 1.8, fill: { color: 'FFFFFF' }, rectRadius: 0.15 });
slide9.addText('Get Started', { x: 1.5, y: 3.75, w: 7, h: 0.4, fontSize: 22, bold: true, color: colors.primary, align: 'center', fontFace: 'Arial' });
slide9.addText([
    { text: 'GitHub: ', options: { bold: true } },
    { text: 'github.com/vibhupb/financial-documents-processing' },
], { x: 1.5, y: 4.2, w: 7, h: 0.35, fontSize: 14, color: colors.dark, align: 'center', fontFace: 'Arial' });
slide9.addText([
    { text: 'Deploy: ', options: { bold: true } },
    { text: 'npm install && cdk deploy --all' },
], { x: 1.5, y: 4.6, w: 7, h: 0.35, fontSize: 14, color: colors.dark, align: 'center', fontFace: 'Arial' });
slide9.addText('~$0.34/doc  |  92.5% savings  |  Production ready',
    { x: 1.5, y: 5.1, w: 7, h: 0.3, fontSize: 12, color: colors.success, align: 'center', fontFace: 'Arial', bold: true });

// Save presentation
const outputPath = path.join(__dirname, '../docs/Financial-Documents-Processing-Router-Pattern.pptx');
pptx.writeFile({ fileName: outputPath })
    .then(() => console.log(`Presentation saved to: ${outputPath}`))
    .catch(err => console.error('Error:', err));
