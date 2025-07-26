# AI-Integrated Adaptive Assessment System  
A Generative AI–Powered Framework for Outcome-Aligned Question Creation in Computing Education

## Overview  
This project presents an AI-integrated assessment design system built to assist educators in generating high-quality, reusable descriptive and multiple-choice questions based on targeted instructional parameters. It supports both scheduled and contextual assessments aligned with Bloom’s Taxonomy, learning outcomes, and domain standards.

## Key Features  
- 🌐 AI-Powered Question Generation using Generative AI APIs  
- 🎯 Targeted Prompts Based on:
  - Topic
  - Course Outcomes
  - Bloom's Cognitive Levels
  - Question Difficulty
  - Mark Weightage  
- 📚 Graph-Based Topic Tagging using ACM Curriculum BoK (Neo4j)  
- 🔁 Reusable Question Bank with Review and Approval Workflow  
- 🧠 Context-Aware Prompting from Learning Environments  
- ✅ Quality Checks: Bloom’s Level Tagging, Difficulty Estimation, Redundancy Detection

## ACM Body of Knowledge Integration  
This project incorporates a graph database modeled on the ACM Curriculum Guidelines’ Body of Knowledge (BoK), using Neo4j. A set of Cypher queries enables automated classification of each generated question based on:
- Knowledge Area (KA)
- Knowledge Unit (KU)
- Associated Learning Outcomes  

These queries help ensure each question is traceable, well-categorized, and suitable for targeted or comprehensive assessment coverage.


## Learning Context Integration  
The system utilizes context data—such as student activity in e-books, videos, and discussion forums—to make question prompts more relevant. This enables support for:
- Teacher-triggered formative assessments  
- Learner-initiated self-assessment  
- Seamless integration with digital learning platforms

## Extensibility  
While currently aligned with the ACM BoK for computing education, the system architecture is flexible and can be adapted to other domain-specific curricula or standardized knowledge models.

## Folder Structure
- instance/ – Local configuration and DB instance
- static/ – CSS, JavaScript, and other static files
- templates/ – Jinja2 HTML templates
- .env – Environment variables (e.g., API keys, database URIs)
- .gitattributes – Git attributes file
- app.py – Main Flask application and route handler







