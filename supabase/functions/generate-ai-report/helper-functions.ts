// Helper functions for the enhanced AI report system

// Extract data types from leaked data description
export function extractDataTypes(whatWasLeaked: string): string[] {
  const text = whatWasLeaked.toLowerCase();
  const dataTypes: string[] = [];
  
  if (text.includes('ssn') || text.includes('social security')) {
    dataTypes.push('Social Security Numbers');
  }
  if (text.includes('credit card') || text.includes('financial') || text.includes('bank')) {
    dataTypes.push('Financial Data');
  }
  if (text.includes('medical') || text.includes('health') || text.includes('hipaa')) {
    dataTypes.push('Medical Records');
  }
  if (text.includes('driver') || text.includes('license') || text.includes('passport')) {
    dataTypes.push('Government ID');
  }
  if (text.includes('biometric') || text.includes('fingerprint') || text.includes('facial')) {
    dataTypes.push('Biometric Data');
  }
  if (text.includes('password') || text.includes('login') || text.includes('credential')) {
    dataTypes.push('Login Credentials');
  }
  if (text.includes('email') || text.includes('phone') || text.includes('address')) {
    dataTypes.push('Contact Information');
  }
  
  return dataTypes.length > 0 ? dataTypes : ['Personal Information'];
}

// Get current year for searches
export function getCurrentYear(): string {
  return new Date().getFullYear().toString();
}

// Score legal sources for prioritization
export function getLegalSourceScore(url: string): number {
  if (url.includes('sec.gov')) return 100;
  if (url.includes('.gov')) return 90;
  if (url.includes('ag.') || url.includes('attorney')) return 85;
  if (url.includes('court') || url.includes('legal')) return 80;
  if (url.includes('law')) return 75;
  if (url.includes('settlement') || url.includes('lawsuit')) return 70;
  return 50;
}

// Check if content cross-verifies breach data
export function crossVerifiesBreachData(content: any, breach: any): boolean {
  if (!content || !content.content) return false;
  
  const contentText = content.content.toLowerCase();
  const orgName = breach.organization_name.toLowerCase();
  
  // Check if the content mentions the organization
  if (!contentText.includes(orgName)) return false;
  
  // Check for breach-related keywords
  const breachKeywords = ['breach', 'incident', 'compromise', 'hack', 'cyber'];
  return breachKeywords.some(keyword => contentText.includes(keyword));
}

// Check if content contains settlement data
export function containsSettlementData(content: any): boolean {
  if (!content || !content.content) return false;
  
  const contentText = content.content.toLowerCase();
  const settlementKeywords = ['settlement', 'class action', '$', 'million', 'per person', 'payout'];
  
  return settlementKeywords.filter(keyword => contentText.includes(keyword)).length >= 2;
}

// Calculate legal settlement range based on data types and precedents
export function calculateLegalSettlementRange(breach: any, dataTypes: string[], content: any[]): any {
  const affectedCount = breach.affected_individuals || 0;
  
  // Base settlement amounts by data type
  const dataTypeValues = {
    'Social Security Numbers': 1500,
    'Medical Records': 1200,
    'Financial Data': 800,
    'Biometric Data': 2500,
    'Government ID': 600,
    'Login Credentials': 300,
    'Contact Information': 150,
    'Personal Information': 200
  };
  
  // Calculate highest value data type
  const maxValue = Math.max(...dataTypes.map(type => dataTypeValues[type] || 200));
  
  // Additional costs
  const creditMonitoring = 240;
  const timeInconvenience = 250;
  const identityProtection = 300;
  
  const perPersonTotal = maxValue + creditMonitoring + timeInconvenience + identityProtection;
  const totalClassValue = affectedCount * perPersonTotal;
  const estimatedSettlement = totalClassValue * 0.3; // Typical 30% of damages
  
  return {
    per_person_range: {
      min: Math.floor(perPersonTotal * 0.5),
      max: perPersonTotal,
      expected: Math.floor(perPersonTotal * 0.7)
    },
    total_class_estimate: {
      min: Math.floor(estimatedSettlement * 0.5),
      max: estimatedSettlement,
      expected: Math.floor(estimatedSettlement * 0.7)
    },
    confidence_level: affectedCount > 0 && dataTypes.length > 0 ? 'High' : 'Medium',
    data_type_analysis: dataTypes.map(type => ({
      type,
      base_value: dataTypeValues[type] || 200,
      precedent_range: `$${(dataTypeValues[type] || 200) * 0.5}-$${dataTypeValues[type] || 200}`
    }))
  };
}