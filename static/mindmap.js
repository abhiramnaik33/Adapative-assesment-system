let treeData;
let selectedLeafTopics = [];

function preload() {
  // Load the JSON data from your Flask backend
  treeData = loadJSON('/static/topics.json');
}

function setup() {
  // Create the canvas for the mindmap
  createCanvas(windowWidth - 100, 600);
  textAlign(CENTER, CENTER);
  // Call function to draw the tree starting from the root
  drawTree(treeData, width / 2, 40);
}

// Function to recursively draw the tree
function drawTree(node, x, y, level = 0) {
  // Draw the node (topic name)
  fill(0);
  text(node.name, x, y);

  // If the node has children (subtopics), draw them recursively
  if (node.children) {
    const step = 150;
    for (let i = 0; i < node.children.length; i++) {
      const childX = x - ((node.children.length - 1) * step / 2) + i * step;
      const childY = y + 80;
      line(x, y + 10, childX, childY - 10);  // Draw line from parent to child
      drawTree(node.children[i], childX, childY, level + 1);
    }
  } else {
    // For leaf nodes (topics with no subtopics), draw an interactive circle
    node.x = x;
    node.y = y;
    ellipse(x, y, 20);  // Draw circle at the node
    fill(255);
    text(node.name, x, y);  // Draw topic name inside the circle
  }
}

// Function to handle topic selection
function mousePressed() {
  traverseAndSelect(treeData);
}

// Function to traverse the tree and detect mouse click on leaf nodes
function traverseAndSelect(node) {
  // Check if the mouse is inside a leaf node circle
  if (!node.children && dist(mouseX, mouseY, node.x, node.y) < 15) {
    // Toggle the selection of the topic (leaf node)
    const idx = selectedLeafTopics.indexOf(node.name);
    if (idx === -1) {
      selectedLeafTopics.push(node.name);  // Add topic if not selected
    } else {
      selectedLeafTopics.splice(idx, 1);  // Remove topic if already selected
    }
    console.log(selectedLeafTopics);  // Log the selected topics for debugging
    updateSelectionDisplay();
  } else if (node.children) {
    // If the node has children, continue traversing
    for (const child of node.children) {
      traverseAndSelect(child);
    }
  }
}

// Function to update the display of selected topics in the form (UI)
function updateSelectionDisplay() {
  // Join the selected topics into a comma-separated string
  const tags = selectedLeafTopics.join(", ");
  document.getElementById("selectedTags").value = tags;  // Update input field in the form
}

// Function to handle opening the modal and triggering the map display
function openModal() {
  // Display the canvas for the mindmap (assuming you have a modal)
  document.getElementById("mindmapCanvas").style.display = "block";
  document.getElementById("selectedTags").value = selectedLeafTopics.join(", ");
}

// Function to close the modal
function closeModal() {
  document.getElementById("mindmapCanvas").style.display = "none";
}
