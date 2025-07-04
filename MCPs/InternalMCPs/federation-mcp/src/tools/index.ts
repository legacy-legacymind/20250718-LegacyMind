import { FederationTool } from '../types/index.js';
import { parallelTaskTool } from './parallelTask.js';
import { researchAndBuildTool } from './researchAndBuild.js';
import { analyzeAndDocumentTool } from './analyzeAndDocument.js';
import { validationAndFixesTool } from './validationAndFixes.js';

export const federationTools: FederationTool[] = [
  parallelTaskTool,
  researchAndBuildTool,
  analyzeAndDocumentTool,
  validationAndFixesTool,
];

export {
  parallelTaskTool,
  researchAndBuildTool,
  analyzeAndDocumentTool,
  validationAndFixesTool,
};