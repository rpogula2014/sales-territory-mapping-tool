export interface AssignmentUpdate {
  accountId: string;
  sellerId: string;
  currentSeller: string;
  assignmentChanged: boolean;
  assignedAt: string;
  assignedBy: string;
  version: number;
}

export interface BulkAssignmentResult {
  updatedCount: number;
  sellerId: string;
  seller: string;
}
