module.exports = function(config) {
  config.set({
    basePath: '',
    frameworks: ['jasmine'],
    files: [
      'lib/jquery.js',
      'lib/underscore.js',
      'lib/backbone.js',
      '../krankshaft/static/js/*.js',
      'spec/*.js'
    ],
    browsers: ['PhantomJS'],
    singleRun: true,
    reporters: ['progress', 'coverage'],
    preprocessors: {
      '../krankshaft/static/js/*.js': ['coverage']
    }
  });
};
