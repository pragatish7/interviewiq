"""
PDF report generation for interview analysis.
Uses reportlab for generating professional PDF reports.
"""
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_pdf_report(interview_data: Dict[str, Any], output_path: str) -> Optional[str]:
    """Generate a comprehensive PDF report for an interview analysis."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm, inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        logger.warning("reportlab not installed. Run: pip install reportlab")
        return _generate_text_report(interview_data, output_path)

    try:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        story = []

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Title'],
            fontSize=24, spaceAfter=6, textColor=colors.HexColor('#1e293b'),
            alignment=TA_CENTER,
        )
        subtitle_style = ParagraphStyle(
            'CustomSubtitle', parent=styles['Normal'],
            fontSize=12, textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER, spaceAfter=20,
        )
        heading_style = ParagraphStyle(
            'CustomHeading', parent=styles['Heading2'],
            fontSize=14, spaceBefore=16, spaceAfter=8,
            textColor=colors.HexColor('#1e293b'),
        )
        body_style = ParagraphStyle(
            'CustomBody', parent=styles['Normal'],
            fontSize=10, leading=14, spaceAfter=4,
            textColor=colors.HexColor('#334155'),
        )
        small_style = ParagraphStyle(
            'Small', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#94a3b8'),
        )

        # Title page
        story.append(Spacer(1, 40 * mm))
        story.append(Paragraph("InterviewIQ", title_style))
        story.append(Paragraph("AI-Powered Interview Performance Report", subtitle_style))
        story.append(HRFlowable(width="60%", thickness=2, color=colors.HexColor('#3b82f6')))
        story.append(Spacer(1, 20 * mm))

        interview = interview_data.get("interview", {})
        interview_title = interview.get("title", "Interview Session")
        created_at = interview.get("created_at", "")
        overall_score = interview.get("overall_score", 0)

        story.append(Paragraph(f"<b>{interview_title}</b>", ParagraphStyle(
            'CenterBold', parent=styles['Normal'],
            fontSize=16, alignment=TA_CENTER, spaceAfter=8,
        )))

        if created_at:
            story.append(Paragraph(f"Date: {created_at[:10]}", ParagraphStyle(
                'Center', parent=styles['Normal'],
                fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor('#64748b'),
            )))

        story.append(Spacer(1, 10 * mm))

        # Overall score box
        score_color = '#22c55e' if overall_score >= 80 else '#f59e0b' if overall_score >= 60 else '#ef4444'
        score_text = f"<font color='{score_color}' size='36'><b>{overall_score}</b></font> / 100"
        story.append(Paragraph(score_text, ParagraphStyle(
            'ScoreCenter', parent=styles['Normal'],
            alignment=TA_CENTER, spaceAfter=4,
        )))

        category = "Excellent" if overall_score >= 90 else "Strong" if overall_score >= 80 else "Good" if overall_score >= 70 else "Needs Improvement" if overall_score >= 60 else "Requires Practice"
        story.append(Paragraph(f"<font color='{score_color}'><b>{category}</b></font>", ParagraphStyle(
            'CatCenter', parent=styles['Normal'],
            fontSize=14, alignment=TA_CENTER, spaceAfter=20,
        )))

        story.append(PageBreak())

        # Score Breakdown
        story.append(Paragraph("Score Breakdown", heading_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
        story.append(Spacer(1, 4 * mm))

        score_data = [
            ['Metric', 'Score', 'Rating'],
            ['Communication', str(interview.get('communication_score', 0) or 0), ''],
            ['Answer Quality', str(interview.get('answer_quality_score', 0) or 0), ''],
            ['Clarity', str(interview.get('clarity_score', 0) or 0), ''],
            ['Fluency', str(interview.get('fluency_score', 0) or 0), ''],
            ['Speaking Pace', str(interview.get('speaking_pace_score', 0) or 0), ''],
            ['Confidence', str(interview.get('confidence_score', 0) or 0), ''],
            ['Vocabulary', str(interview.get('vocabulary_score', 0) or 0), ''],
            ['Relevance', str(interview.get('relevance_score', 0) or 0), ''],
            ['Professionalism', str(interview.get('professionalism_score', 0) or 0), ''],
            ['Visual Presentation', str(interview.get('nonverbal_score', 0) or 0), ''],
        ]

        table = Table(score_data, colWidths=[150, 80, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#475569')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 8 * mm))

        # Speech Metrics
        story.append(Paragraph("Speech Analysis", heading_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
        story.append(Spacer(1, 4 * mm))

        speech_items = [
            f"Words Per Minute: {interview.get('words_per_minute', 0) or 0}",
            f"Filler Words: {interview.get('filler_count', 0) or 0} ({interview.get('filler_rate', 0) or 0}/min)",
            f"Pauses: {interview.get('pause_count', 0) or 0}",
            f"Total Words: {interview.get('total_words', 0) or 0}",
            f"Total Sentences: {interview.get('total_sentences', 0) or 0}",
            f"Vocabulary Diversity: {interview.get('vocabulary_diversity', 0) or 0}",
        ]
        for item in speech_items:
            story.append(Paragraph(f"• {item}", body_style))

        story.append(Spacer(1, 8 * mm))

        # Coaching Feedback
        coaching = interview_data.get("coaching", {})
        if coaching:
            story.append(Paragraph("Personalized Coaching", heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
            story.append(Spacer(1, 4 * mm))

            if coaching.get("overall_assessment"):
                story.append(Paragraph(f"<i>{coaching['overall_assessment']}</i>", body_style))
                story.append(Spacer(1, 4 * mm))

            story.append(Paragraph("<b>Strengths:</b>", body_style))
            for s in coaching.get("strengths", []):
                story.append(Paragraph(f"✓ {s}", body_style))

            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("<b>Areas for Improvement:</b>", body_style))
            for i in coaching.get("improvements", []):
                story.append(Paragraph(f"→ {i}", body_style))

        story.append(PageBreak())

        # Improvement Plan
        plan = interview_data.get("improvement_plan", [])
        if plan:
            story.append(Paragraph("7-Day Improvement Plan", heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
            story.append(Spacer(1, 4 * mm))

            for day in plan:
                story.append(Paragraph(
                    f"<b>Day {day.get('day', 0)}: {day.get('title', '')}</b>",
                    body_style
                ))
                story.append(Paragraph(f"Focus: {day.get('focus', '')}", small_style))
                story.append(Paragraph(day.get('exercise', ''), body_style))
                story.append(Paragraph(f"Target: {day.get('target', '')}", small_style))
                story.append(Spacer(1, 4 * mm))

        # Q&A Analysis
        qa_analysis = interview_data.get("qa_analysis", [])
        if qa_analysis:
            story.append(PageBreak())
            story.append(Paragraph("Answer Analysis", heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
            story.append(Spacer(1, 4 * mm))

            for qa in qa_analysis[:10]:
                if qa.get("question"):
                    story.append(Paragraph(
                        f"<b>Q:</b> {qa['question'][:200]}",
                        body_style
                    ))
                    story.append(Paragraph(
                        f"<b>Score:</b> {qa.get('overall_answer_score', 0)}/100",
                        small_style
                    ))
                    if qa.get("strengths"):
                        for s in qa["strengths"]:
                            story.append(Paragraph(f"  + {s}", small_style))
                    story.append(Spacer(1, 4 * mm))

        # Footer
        story.append(Spacer(1, 20 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
        story.append(Paragraph(
            f"Generated by InterviewIQ on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            ParagraphStyle('Footer', parent=styles['Normal'],
                          fontSize=8, textColor=colors.HexColor('#94a3b8'),
                          alignment=TA_CENTER, spaceAfter=4)
        ))
        story.append(Paragraph(
            "AI-Powered Mock Interview Performance Analyzer",
            ParagraphStyle('Footer2', parent=styles['Normal'],
                          fontSize=8, textColor=colors.HexColor('#94a3b8'),
                          alignment=TA_CENTER)
        ))

        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return _generate_text_report(interview_data, output_path)


def _generate_text_report(data: Dict[str, Any], output_path: str) -> Optional[str]:
    """Fallback: generate a text report if reportlab isn't available."""
    try:
        text_path = output_path.replace('.pdf', '.txt')
        interview = data.get("interview", {})
        coaching = data.get("coaching", {})

        with open(text_path, 'w', encoding='utf-8') as f:
            f.write("InterviewIQ - Interview Performance Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Title: {interview.get('title', 'Interview')}\n")
            f.write(f"Date: {interview.get('created_at', 'N/A')}\n\n")
            f.write(f"Overall Score: {interview.get('overall_score', 0)}/100\n\n")
            f.write("Score Breakdown:\n")
            for key in ['communication_score', 'answer_quality_score', 'clarity_score',
                        'fluency_score', 'confidence_score', 'vocabulary_score']:
                label = key.replace('_score', '').replace('_', ' ').title()
                f.write(f"  {label}: {interview.get(key, 0)}/100\n")
            f.write("\nStrengths:\n")
            for s in coaching.get("strengths", []):
                f.write(f"  • {s}\n")
            f.write("\nImprovements:\n")
            for i in coaching.get("improvements", []):
                f.write(f"  • {i}\n")

        return text_path
    except Exception as e:
        logger.error(f"Text report generation failed: {e}")
        return None
